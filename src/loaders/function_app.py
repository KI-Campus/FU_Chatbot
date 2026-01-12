import os
import sys

import azure.functions as func

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from get_data import Fetch_Data

app = func.FunctionApp()


@app.function_name(name="timer_trigger")
@app.timer_trigger(schedule="0 0 5 * * 4", arg_name="mytimer", run_on_startup=True, use_monitor=False)
def timer_trigger(mytimer: func.TimerRequest) -> None:
    Fetch_Data().extract()


@app.function_name(name="manual_trigger")
@app.route(route="manual_ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Manually trigger data ingestion via HTTP POST request."""
    try:
        Fetch_Data().extract()
        return func.HttpResponse("Data ingestion completed successfully!", status_code=200)
    except Exception as e:
        return func.HttpResponse(f"Data ingestion failed: {str(e)}", status_code=500)
