import os
import sys
import json
import logging

import azure.functions as func
import azure.durable_functions as df

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from get_data import Fetch_Data
from run_logger import RunLogger, create_run_log_sas_url

app = func.FunctionApp()


# =============================================================================
# DURABLE FUNCTIONS PATTERN
# =============================================================================

# 1. HTTP Starter - Starts the orchestration and returns status URLs
@app.function_name(name="start_ingest")
@app.route(route="start_ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
@app.durable_client_input(client_name="client")
async def start_ingest(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    """Start the durable data ingestion orchestration."""
    # Reject overlapping runs: start with a deterministic singleton instance_id.
    # Durable will throw if an instance with that id already exists.
    singleton_instance_id = "ingest_singleton"

    # If a previous instance is still running, reject.
    existing = await client.get_status(singleton_instance_id)
    if existing and existing.runtime_status and existing.runtime_status.name in {"Running", "Pending"}:
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "INGEST_ALREADY_RUNNING",
                    "instanceId": singleton_instance_id,
                    "runtimeStatus": existing.runtime_status.name,
                    "statusQueryGetUri": client.create_check_status_response(req, singleton_instance_id).headers.get(
                        "Location"
                    ),
                }
            ),
            status_code=409,
            mimetype="application/json",
        )

    # If a previous singleton instance completed/failed/terminated, purge its history so we can
    # re-use the deterministic instance id.
    if existing and existing.runtime_status and existing.runtime_status.name in {"Completed", "Failed", "Terminated"}:
        try:
            await client.purge_instance_history(singleton_instance_id)
        except Exception:
            # best-effort; Durable may already have purged or not support purge in this context
            pass

    # Generate a run_id now so we can expose a log URL immediately.
    run_id = RunLogger.new_run_id()
    log_url = create_run_log_sas_url(run_id, expiry_hours=24)

    instance_id = await client.start_new(
        "ingest_orchestrator",
        singleton_instance_id,
        {"run_id": run_id, "log_url": log_url},
    )
    logging.info(f"Started orchestration with ID = '{instance_id}' (run_id={run_id})")

    # Return the standard Durable status URLs + our run metadata so the caller can
    # open the log URL while the run is still executing.
    status_response = client.create_check_status_response(req, instance_id)
    body = {
        "instanceId": instance_id,
        "run_id": run_id,
        "log_url": log_url,
        "statusQueryGetUri": status_response.headers.get("Location"),
        "sendEventPostUri": status_response.headers.get("Location"),
        "terminatePostUri": status_response.headers.get("Location"),
        "purgeHistoryDeleteUri": status_response.headers.get("Location"),
    }
    return func.HttpResponse(json.dumps(body), status_code=202, mimetype="application/json")


# 2. Orchestrator - Coordinates the workflow, survives restarts
@app.function_name(name="ingest_orchestrator")
@app.orchestration_trigger(context_name="context")
def ingest_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrator that coordinates data ingestion activities."""
    payload = context.get_input() or {}
    # Call the activity function that does the actual work
    result = yield context.call_activity("run_data_extraction", payload)
    return result


# 3. Activity Function - Does the actual work
@app.function_name(name="run_data_extraction")
@app.activity_trigger(input_name="payload")
def run_data_extraction(payload) -> str:
    """Activity that performs the actual data extraction."""
    logger = logging.getLogger("loader")
    logger.info("Starting data extraction activity...")
    try:
        run_id = None
        preset_log_url = None
        if isinstance(payload, dict):
            run_id = payload.get("run_id")
            preset_log_url = payload.get("log_url")

        logger.info("Activity payload received (run_id=%s)", run_id)
        result = Fetch_Data(run_id=run_id, preset_log_url=preset_log_url).extract()
        # Durable Functions will JSON-serialize dict outputs.
        return result
    except Exception as e:
        logger.exception("Data extraction failed")
        raise


# 4. Status Check Endpoint - Check orchestration status
@app.function_name(name="check_status")
@app.route(route="check_status/{instance_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
@app.durable_client_input(client_name="client")
async def check_status(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    """Check the status of a running orchestration."""
    instance_id = req.route_params.get("instance_id")
    status = await client.get_status(instance_id)
    if status:
        return func.HttpResponse(
            json.dumps({
                "instanceId": status.instance_id,
                "runtimeStatus": status.runtime_status.name,
                "output": status.output,
                "createdTime": str(status.created_time),
                "lastUpdatedTime": str(status.last_updated_time),
            }),
            mimetype="application/json"
        )
    return func.HttpResponse("Instance not found", status_code=404)


# =============================================================================
# LEGACY TRIGGERS (kept for backwards compatibility)
# =============================================================================

@app.function_name(name="timer_trigger")
@app.timer_trigger(schedule="0 0 5 * * 4", arg_name="mytimer", run_on_startup=False, use_monitor=False)
@app.durable_client_input(client_name="client")
async def timer_trigger(mytimer: func.TimerRequest, client: df.DurableOrchestrationClient) -> None:
    """Weekly timer that starts the durable orchestration."""
    singleton_instance_id = "ingest_singleton"
    existing = await client.get_status(singleton_instance_id)
    if existing and existing.runtime_status and existing.runtime_status.name in {"Running", "Pending"}:
        logging.warning(
            "Timer ingest skipped because a run is already active (instanceId=%s status=%s)",
            singleton_instance_id,
            existing.runtime_status.name,
        )
        return

    if existing and existing.runtime_status and existing.runtime_status.name in {"Completed", "Failed", "Terminated"}:
        try:
            await client.purge_instance_history(singleton_instance_id)
        except Exception:
            pass

    run_id = RunLogger.new_run_id()
    log_url = create_run_log_sas_url(run_id, expiry_hours=24)
    instance_id = await client.start_new("ingest_orchestrator", singleton_instance_id, {"run_id": run_id, "log_url": log_url})
    logging.info(f"Timer started orchestration with ID = '{instance_id}' (run_id={run_id})")


@app.function_name(name="manual_trigger")
@app.route(route="manual_ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Legacy manual trigger - consider using /api/start_ingest instead."""
    try:
        Fetch_Data().extract()
        return func.HttpResponse("Data ingestion completed successfully!", status_code=200)
    except Exception as e:
        return func.HttpResponse(f"Data ingestion failed: {str(e)}", status_code=500)
