from flask import Flask, redirect, url_for, session, request, jsonify, render_template, flash
from markupsafe import Markup
#from flask_apscheduler import APScheduler
#from apscheduler.schedulers.background import BackgroundScheduler
from flask_oauthlib.client import OAuth
from bson.objectid import ObjectId
from pymongo import DESCENDING
from bson.objectid import ObjectId

import pprint
import os
import time
import pymongo
import sys
 
app = Flask(__name__)

app.debug = False #Change this to False for production
#os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' #Remove once done debugging

app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)
oauth.init_app(app) #initialize the app to be able to make requests for user information

#Set up GitHub as OAuth provider
github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'], #your web app's "username" for github's OAuth
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],#your web app's "password" for github's OAuth
    request_token_params={'scope': 'user:email'}, #request read-only access to the user's email.  For a list of possible scopes, see developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',  
    authorize_url='https://github.com/login/oauth/authorize' #URL for github's OAuth login
)

#Connect to database
url = os.environ["MONGO_CONNECTION_STRING"]
client = pymongo.MongoClient(url)
db = client[os.environ["MONGO_DBNAME"]]
collection = db['posts'] #TODO: put the name of the collection here
forumsposts = db['forums']
storyRepo=db['Worlds']
repositoryDATA = db['repository']

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

#context processors run before templates are rendered and add variable(s) to the template's context
#context processors must return a dictionary 
#this context processor adds the variable logged_in to the conext for all templates
@app.context_processor
def inject_logged_in():
    return {"logged_in":('github_token' in session)}

@app.route('/')
def home():
    return render_template('home.html')
@app.route('/edit')
def edits():
    return render_template('edit.html')
#redirect to GitHub's OAuth page and confirm callback URL
@app.route('/login')
def login():   
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='http')) #callback URL must match the pre-configured callback URL

@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out.')
    return redirect('/')

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        flash('Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args), 'error')      
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            message = 'You were successfully logged in as ' + session['user_data']['login'] + '.'
        except Exception as inst:
            session.clear()
            print(inst)
            message = 'Unable to login, please try again.', 'error'
    return render_template('message.html', message=message)


@app.route('/page1')
def renderPage1():
    postPostPost=renderTheForum()
    return render_template('page1.html', postPostPost=postPostPost)
@app.route('/page2')
def renderPage2():
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            titleStory=returnTitle()
            summary=returnSummary()
            mainc=returnMaincharacter()
            world=returnWorld()
            enemy=returnEnemy()
        else:
            titleStory="No Title Yet"
            summary="No Summary Yet"
            mainc="No Main Character Yet"
            world="No World Yet"
            enemy="No Enemy Yet"
    return render_template('page2.html', titleStory=titleStory, summary=summary,mainc=mainc, world=world, enemy=enemy)
    
@app.route('/answerForumOne',methods=['GET','POST'])
def renderForumOneAnswers():
    #if "user_data" in session:
    forumPost=request.form['ques1']
    forumTitle=request.form['ques2']
    doc = {"username":session['user_data']['login'], "name":forumTitle,"text":forumPost}
    
    forumsposts.insert_one(doc)
    postPostPost=renderTheForum()

    return render_template('page1.html', postPostPost=postPostPost)
@app.route('/makeIt', methods=['GET', 'POST'])
def makeStory():
    if request.method == 'GET':
        return render_template('make.html')
    
    elif request.method == 'POST':
        existing_story = storyRepo.find_one({'username': session['user_data']['login']})
        if existing_story:
            return render_template('message.html', message='You Already have a story.')
        
        title = request.form.get('ques231')
        summary = request.form.get('ques232')
        world = request.form.get('ques233')
        mainc = request.form.get('ques234')
        enemy = request.form.get('ques235')
        
        doc = {
            "username": session['user_data']['login'],
            "title": title,
            "summary": summary,
            "maincharacter": mainc,
            "world": world,
            "enemy": enemy
        }
        storyRepo.insert_one(doc)
        
        return redirect('/page2')
       
@app.route('/changeIt', methods=['GET', 'POST'])
def changeSummary():
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            if request.method == 'POST':
                choice = request.form.get("choices")
                new_content = request.form['ques23']
                username = session.get('user_data', {}).get('login')
                if not username:
                    return "User not logged in", 401
                print(f"Attempting t vjch {choice} for user: {username}")
                print(f"New content: {new_content}")
                valid_choices = ['summary', 'titleStory', 'world', 'maincharacter', 'enemy']
                if choice not in valid_choices:
                    return "Invalid choice", 400
                result = storyRepo.update_one(
                    {'username': username},
                    {'$set': {choice: new_content}}
                )
                print(f"Update result: Matched: {result.matched_count}, Modified: {result.modified_count}")
                if result.modified_count > 0:
                    return f"{choice.capitalize()} updated successfully"
                elif result.matched_count > 0:
                    return "No changes were made"
                else:
                    return "User not found", 404
    
    return render_template('edit.html')
#got help from perplexity because its confusing    

    
#the tokengetter is automatically called to check who is logged in.
def renderTheForum():
    option = []
    for s in forumsposts.find().sort('_id', DESCENDING):
        formatted_post = f"<pre><h3>{s['username']}-{s['name']}</h3><br><h3>{s['text']}</h3></pre><br>"
        option.append(formatted_post)

    return Markup("".join(option))   
def returnTitle():
    title=""
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            title=s['title']
    return s['title']
def returnSummary():
    title=""
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            title=s['summary']
    return title
def returnMaincharacter():
    title=""
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            title=s['maincharacter']
    return title
def returnWorld():
    title=""
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            title=s['world']
    return title
def returnEnemy():
    title=""
    for s in storyRepo.find():
        if s['username']==session['user_data']['login']:
            title=s['enemy']
    return title
    
    
    
    
@github.tokengetter
def get_github_oauth_token():
    return session['github_token']


if __name__ == '__main__':
    app.run()
