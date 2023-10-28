	from flask import render_template, url_for, request, redirect, session, flash, abort, make_response, send_file
from flask_login import login_user, logout_user, current_user, login_required  # , AnonymousUserMixin
from webapp import app, db, nav, login_manager, socketio
from webapp.models import User, PersistentStorage as PS
from webapp.models import post_collection, external_user
from webapp.forms import LoginForm, RegistrationForm
from datetime import datetime, timedelta
import base64
import hashlib
from validate_email import validate_email
from flask_socketio import emit  # , join_room, leave_room, send,
# from time import sleep


def gen_nav():
	"""
	function for generating nav bar links for each user type

	:authors:
		- Matt
	:return: None
	"""
	#
	nav.Bar('guest', [
		nav.Item(' Home', 'home'),
		# nav.Item('Register', 'register', html_attrs={'class': 'right'}),
		nav.Item(' Login', 'login', html_attrs={'class': 'bottom'}),
		# nav.Item('Logout', 'logout', html_attrs={'class': ["right"]}),
	])

	# try:
	# 	user_profile_link = nav.Item(getattr(current_user, 'username'), 'user', html_attrs={'class': 'right'})
	# except AttributeError:
	# 	user_profile_link = nav.Item(' User', 'user', html_attrs={'class': 'right'})

	nav.Bar('viewer', [
		nav.Item(' Home', 'home', html_attrs={'icon': 'home.svg'}),
		nav.Item(' Map Test', 'map_test', html_attrs={'icon': 'map.svg'}),
		nav.Item(' Logout', 'logout', html_attrs={'class': 'bottom', 'icon': 'logout.svg'}),
		# user_profile_link,
	])

	nav.Bar('admin', [
		nav.Item(' Home', 'home'),
		nav.Item(' Map Test', 'map_test', html_attrs={'icon': 'map.svg'}),
		nav.Item(' Logout', 'logout', html_attrs={'class': 'bottom', 'icon': 'logout.svg'}),
		# user_profile_link,
	])


@app.before_request
def before_request():
	"""
	function to be ran before every request.

	:authors:
		- Matt
	:return: None
	"""
	# generate the nav bar
	gen_nav()

	# some session crap
	session.permanent = True
	app.permanent_session_lifetime = timedelta(minutes=20)
	session.modified = True

	# saves requested endpoint to session to be redirected after login if unauthenticated
	# TODO work out why the test page isn't being redirected to after login
	if request.endpoint not in ['js', 'css', 'icons', 'login', None, 'logout', 'mcss', 'static_loader']:
		session['url'] = request.url
	# print(session['url'])
	# print(request.endpoint)
	else:
		session['url'] = url_for("home")


@app.route("/", methods=["GET"])
def landing():
	"""
	GET:
		description: redirects to /home

		security: None required

		responses:
			302: redirects to "/home"

	:authors:
		- Matt
	:returns: HTTP Response
	"""
	return redirect(url_for("home"))


@login_required
@app.route("/home", methods=["GET"])
def home():
	"""
	GET:
		description: homepage/dashboard for the webapp

		security: User Authentication Required

		responses:
			200: returns rendered dashboard template

			302: redirect to login page

	:authors:
		- Matt
	:returns: HTTP Response
	"""
	if current_user.is_authenticated:  # only show homepage to logged in users
		# collate data from sources to display in the dashboard
		display_data = {
			"Total Posts": {  # TODO update post totals to be live data rather than placeholders
				"Twitter": ("4.2k", "int",),
				"Flickr": ("69", "int",)
			},
			"Average Sentiment": {  # TODO update product sentiments to be live data rather than placeholders
				"Product": (4.2, "scale", 5,),
				"Competitor": (0.3, "scale", 5,)
			},
			"Twitter": {  # TODO duplicate this section for flickr scraper once integrated
				"Last Scrape": (
					datetime.fromisoformat(PS.query.filter_by(id="last_tweet_scrape_time").first().content)
						.strftime("%H:%M:%S"),
					"timestamp", "last_twitter_scrape_timestamp",
				),
				"Next Scrape": (
					(datetime.fromisoformat(PS.query.filter_by(id="last_tweet_scrape_time").first().content)
					+ timedelta(seconds=30)).timestamp(),
					"countdown",
					(datetime.fromisoformat(PS.query.filter_by(id="last_tweet_scrape_time").first().content)
					+ timedelta(seconds=0)).timestamp(),
					"tweet_scrape_cd",
				)
			}
		}
		live_update_cds = ["tweet_scrape_cd"]
		# define the javascript and css files need to be loaded by the template engine
		js_files = ["dashboard.js"]
		css_files = ["dashboard.css"]
		return render_template('home.html', title="Home", hide_nav=False,
								dashboard_values=display_data, template_js_files=js_files,
								template_css_files=css_files, luc=live_update_cds)
	else:
		# send un-logged in users to the login page
		return redirect(url_for("login"))


@login_required
@app.route("/map_test", methods=["GET"])
def map_test():
	return render_template('map_test.html', title="Map Test", hide_nav=False)

@login_required
@app.route("/test", methods=["GET"])
def test():
	"""
	GET:
		description: Matts test page for trying out experimental code and css etc

		security: User Authentication Required

		responses:
			200: returns test.html

			302: redirect to login page

	:authors:
		- Matt
	:returns: HTTP Response
	"""
	if current_user.is_authenticated:  # only show page to logged in users

		js_files = ["test.js"]
		return render_template('test.html', hide_nav=False, template_js_files=js_files)
	else:
		# send un-logged in users to the login page
		return redirect(url_for("login"))


# socket io testing
# TODO clean up, remove if not needed
@socketio.on('test', namespace="/test")
def handle_message(data):
	print(str(data))
	print('received message: ' + str(data["data"]))
	data_out = datetime.fromisoformat(PS.query.filter_by(id="last_tweet_scrape_time").first().content).strftime(
		"%H:%M:%S")
	emit('test', {'data': data_out}, broadcast=True)


# more different socket io testing
# TODO clean up, remove if not needed
@socketio.on('connect', namespace="/test")
def handle_connect():
	print("connection made")


@app.route("/login", methods=["GET", "POST"])
def login():
	"""
	GET:
		description: login / register page

		security: None required

		responses:
			200: returns rendered login template

	POST:
		description: login / register page

		security: None required

		responses:
			200: if login or register fails, loads self again

			302: redirects to previously request page or, if not known, the homepage

	:authors:
		- Matt
	:returns: HTTP Response
	"""
	# TODO: show why the form failed to submit (i.e. "wrong password")

	# instantiate form objects
	login_form = LoginForm()
	register_form = RegistrationForm()

	if request.method == "GET":
		if current_user.is_authenticated:
			# Don't allow logged in users to access the login/register page
			return redirect(url_for("home"))
	else:
		# default the form type to "login" to get rid of a pesky warning
		form_type = "login"
		try:
			# get string to identify if the login form or the register form was submitted
			# this took way to fucking long to get working omg
			form_type = request.form["form_type"]
		except KeyError:
			abort(404)
		if form_type == "register":  # process user registration form
			# collate inputted details as variables
			email = str(register_form.email.data)
			username = str(register_form.username.data)
			password = str(register_form.password.data)

			# generating user id as a random string based on entered info
			i = 1
			id_base = email + username + str(i)
			taken_ids = User.query.with_entities(User.id).all()
			while (new_id := str(base64.urlsafe_b64encode(hashlib.md5(str(id_base).encode('utf-8')).digest()),
									'utf-8').rstrip("=")[0:15]) in taken_ids:
				# make sure the generated id hasn't been taken and if it has,
				#   keep generating new ones until unique id has been found
				i += 1
				id_base = email + username + str(i)

			# add new user to the database
			new_user = User(id=new_id, username=username, email=email, password=password, role="viewer")
			db.session.add(new_user)
			db.session.commit()

			# automagically log in the user once they have registered
			login_user(new_user)
			if session['url']:
				return redirect(session['url'])
			else:
				return redirect(url_for('home'))

		elif form_type == "login":  # process user login form
			if validate_email(login_form.email.data):  # check for email
				user = User.query.filter_by(email=login_form.email.data).first()

			else:  # if email wasn't found, assume username was entered and login with that instead
				user = User.query.filter_by(username=login_form.email.data).first()

			if user is not None:  # check there is a user for the provided username or email
				# check the hash of the entered password matches the stored hash
				if user.verify_password(login_form.password.data):
					# log in the user then redirect to last accessed url on our site
					login_user(user)
					return redirect(session['url'])
		else:
			abort(404)

	# checking if the user is not authenticated, redirect to home if they are otherwise display the login page
	if current_user.is_authenticated:
		return redirect(url_for(home))
	else:
		# set javascript and css files to be loaded by the template engine
		js_files = ["login.js"]
		css_files = ["login.css"]
		return render_template('login.html', title="Login", hide_nav=True, login=login_form,
								register=register_form, template_js_files=js_files,
								template_css_files=css_files)


@app.route("/logout", methods=["GET"])
def logout():
	"""
	GET:
		description: route for logging out a user

		security: None required

		responses:
			302: redirect to login page

	:authors:
		- Matt
	:returns: HTTP Response
	"""
	logout_user()
	flash("Logged Out")
	return redirect(url_for("login"))


@login_manager.user_loader
def load_user(user_id: str):
	"""
	Seems to load the current user, not sure why its needed

	:authors:
		- Matt
	:param user_id: string of a user id
	:returns: User class from models.py referencing the database
	"""
	return User.query.get(str(user_id))


# icon loader - DEPRECATED
@app.route("/icons/<string:filename>", methods=["GET"])
def icons(filename): # TODO: confirm this is legacy and remove if necessary.
	response = make_response(
		send_file((app.config['ROOT_FOLDER'] + "/webapp/static/icons/" + filename).replace("\\", "/")))
	response.headers['mimetype'] = 'image/svg+xml'
	return response


# static files loader route, capable of loading multiple files of either js or css but not together
# TODO add caching for previously requested file lists
@app.route("/static", methods=["GET"])
def static_loader():
	"""
	GET:
		description: single route for requesting concatenated static files, either JS or CSS

		args:
			t: type of file, either "js" or "css"

			q: filenames of requested files in order, separated by "&" in the url

		security: None required

		responses:
			200: returns the requested js or css files all concatenated together

			404: error not found if the requested filetype is neither js or css

	:authors:
		- Matt
	:returns: HTTP Response
	"""
	# lookup table for mimetypes
	mimetype_lookup = {
		"js": "text/javascript",
		"css": "text/css"
	}
	# load url args from request object
	args = request.args
	filetype = args["t"]
	if filetype in ["js", "css"]:
		file_list = args["q"].split(" ")
		output = []
		for file in file_list:
			# load and concatenate all of the requested files
			with open(
					str(app.config['ROOT_FOLDER'] + "/webapp/static/" + filetype + "/" + file).replace("\\", "/"),
					"r") as contents:
				output.append(contents.read())
		# create http response from concatenated files
		response = make_response("\n".join(output))
		# set correct mimetype for response
		response.mimetype = mimetype_lookup[filetype]
		return response
	else:
		abort(404)
