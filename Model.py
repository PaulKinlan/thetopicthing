#!/usr/bin/env python

from google.appengine.ext import db

class SearchProvider(db.Model):
    'Information about the sources that we must search'
    FriendlyName = db.StringProperty()
    Name = db.StringProperty()
    HtmlUrl = db.StringProperty()
    FeedUrl = db.StringProperty()
    FeedType = db.StringProperty(default = 'RSS', choices = ['RSS', 'ATOM', 'JSON', 'XML'])
    Category = db.StringProperty(default = 'General', choices = ['General', 'Tech', 'Sport', 'Related'])
    Priority = db.IntegerProperty(default = 1)

class SearchTerm(db.Model):
    'A Search object is a record of a search that has been performed.  Currently just stores the text and the vertical result.'
    term = db.StringProperty(required = True)
    firstQueryDateTime = db.DateTimeProperty(auto_now_add = True)
    type = db.StringProperty(default = 'Unclassified', choices = [None, 'Safe', 'Unclassified', 'Porn', 'Spam', 'Hate', 'Gambling', 'Hacking', 'Drugs', 'Pharma'])

class SearchResult(db.Model):
    'A Search Result for a given search term'
    SearchTerm = db.ReferenceProperty(SearchTerm)
    SearchProvider = db.ReferenceProperty(SearchProvider)
    Added_On = db.DateTimeProperty(auto_now_add = True)
    Last_Accessed = db.DateTimeProperty(auto_now = True)
    Result = db.TextProperty()