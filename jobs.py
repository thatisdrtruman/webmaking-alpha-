from webapp import scheduler, db, socketio, app
from webapp.models import PersistentStorage as PS
import datetime
from flask_socketio import join_room, leave_room, send, emit


# scheduler task for running the twitter scraper function based on interval set in database
@scheduler.task('interval', id='twitter_scraper', seconds=int(app.ps_cache["twitter_scrape_interval"]), misfire_grace_time=900)
def twitter_scraper():
	current_datetime = datetime.datetime.utcnow()

	# get current iso timestamp
	timestamp = current_datetime.isoformat()

	# store current iso timestamp in database and persistent cache
	app.ps_cache["last_tweet_scrape_time"] = timestamp
	PS.query.filter_by(id="last_tweet_scrape_time").first().content = timestamp
	db.session.commit()

	# debug statement for job execution time
	# print('Job 1 executed - ', current_datetime.strftime("%H:%M:%S"))

	# notify dashboard of executed job and update with new info
	socketio.emit('twitter_scraper_update', {
			"last_time": current_datetime.timestamp(),
			"next_time": current_datetime.timestamp() + int(app.ps_cache["twitter_scrape_interval"]),
			"interval": int(app.ps_cache["twitter_scrape_interval"])
		}, broadcast=True, namespace="/dashboard")
