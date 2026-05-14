from flask import Flask
from google.appengine.api import wrap_wsgi_app

import _memcache_compat  # noqa: F401
import BatchRankings
import BotCompare
import BotDetails
import FetchParseFlags
import HandleQueuedResults
import Rankings
import RatingsFile
import RemoveOldParticipant
import RumbleSelect
import RumbleStats
import UploadedResults
from auth import require_admin, require_cron, require_task

app = Flask(__name__)
app.wsgi_app = wrap_wsgi_app(app.wsgi_app)

app.add_url_rule("/", view_func=RumbleSelect.rumble_select, methods=["GET"])
app.add_url_rule("/RumbleSelect", view_func=RumbleSelect.rumble_select, methods=["GET"])
app.add_url_rule("/Rankings", view_func=Rankings.rankings, methods=["GET"])
app.add_url_rule("/RatingsFile", view_func=RatingsFile.ratings_file, methods=["GET"])
app.add_url_rule("/BotDetails", view_func=BotDetails.bot_details, methods=["GET"])
app.add_url_rule("/BotCompare", view_func=BotCompare.bot_compare, methods=["GET"])
app.add_url_rule("/RumbleStats", view_func=RumbleStats.rumble_stats, methods=["GET"])
app.add_url_rule("/UploadedResults", view_func=UploadedResults.uploaded_results, methods=["POST"])

app.add_url_rule(
    "/FetchParseFlags",
    view_func=require_cron(FetchParseFlags.fetch_parse_flags),
    methods=["GET"],
)
app.add_url_rule(
    "/HandleQueuedResults",
    view_func=require_task(HandleQueuedResults.handle_queued_results),
    methods=["POST"],
)
app.add_url_rule(
    "/RemoveOldParticipant",
    view_func=RemoveOldParticipant.remove_old_participant,
    methods=["GET", "POST"],
)
app.add_url_rule(
    "/QueueBatchRankings",
    view_func=require_admin(BatchRankings.queue_batch_rankings),
    methods=["GET"],
)
app.add_url_rule(
    "/QueueDailyBatchRankings",
    view_func=require_cron(BatchRankings.queue_daily_batch_rankings),
    methods=["GET"],
)
