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
    instance_id = await client.start_new("ingest_orchestrator", None, None)
    logging.info(f"Started orchestration with ID = '{instance_id}'")
    return client.create_check_status_response(req, instance_id)


# 2. Orchestrator - Coordinates the workflow, survives restarts
@app.function_name(name="ingest_orchestrator")
@app.orchestration_trigger(context_name="context")
def ingest_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrator that coordinates data ingestion activities."""
    # Call the activity function that does the actual work
    result = yield context.call_activity("run_data_extraction", None)
    return result


# 3. Activity Function - Does the actual work
@app.function_name(name="run_data_extraction")
@app.activity_trigger(input_name="payload")
def run_data_extraction(payload) -> str:
    """Activity that performs the actual data extraction."""
    logging.info("Starting data extraction activity...")
    try:
        Fetch_Data().extract()
        return "Data ingestion completed successfully!"
    except Exception as e:
        logging.error(f"Data extraction failed: {str(e)}")
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
    instance_id = await client.start_new("ingest_orchestrator", None, None)
    logging.info(f"Timer started orchestration with ID = '{instance_id}'")


@app.function_name(name="manual_trigger")
@app.route(route="manual_ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Legacy manual trigger - consider using /api/start_ingest instead."""
    try:
        Fetch_Data().extract()
        return func.HttpResponse("Data ingestion completed successfully!", status_code=200)
    except Exception as e:
        return func.HttpResponse(f"Data ingestion failed: {str(e)}", status_code=500)
