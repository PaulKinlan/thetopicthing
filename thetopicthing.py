#!/usr/bin/env python

import wsgiref.handlers;

import Model
import Url

import re
import os
import unicodedata
import simplejson
import urllib
import datetime
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import memcache

from google.appengine.api import urlfetch

def memoize(keyformat, time=60):
    """Decorator to memoize functions using memcache."""
    def decorator(fxn):
        def wrapper(*args, **kwargs):
            key = keyformat % args[0:keyformat.count('%')]
            data = memcache.get(key)
            if data is not None:
                return data
            data = fxn(*args, **kwargs)
            memcache.set(key, data, time)
            return data
        return wrapper
    return decorator

def ParseSimpleStringTag(tag, data):
    
    data = data.replace('\t', '')
    data = data.replace('\n', '')
    
    match = re.search('<' + tag + '([^>]*?)><!\[CDATA\[(.*?)\]\]></' + tag + '>', data, re.DOTALL|re.I|re.M|re.S)
    
    if match is not None:
        return match.group(2)
    else:
        match = re.search('<' + tag + '([^>]*?)>(.*?)</' + tag + '>', data, re.DOTALL|re.I|re.M|re.S)
        if match is not None:
            return match.group(2)

def ParseSimpleDateTag(tag, data):
    match = re.search('<' + tag + '>(\d\d\d\d)-(\d\d)-(\d\d)</' + tag + '>', data, re.DOTALL|re.I|re.M)
    
    if match is not None:
        return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        return datetime.date(1900,1,1)
    
def ParseSimpleBoolTag(tag, data):
    match = re.search('<' + tag + '>(True)|(False)|(1)|(0)</' + tag + '>', data, re.DOTALL|re.I|re.M)
    
    if match is not None:
        if match.group(1) == 'True' or match.group(2) == '1':
            return True
        else:
            return False
        
    return False

class Result:
    def __init__(self, title, abstract, site, url):
        self.title = title
        self.abstract = abstract
        self.url = url
        self.site = site
        self.id = re.sub("\.","", site)
        
class RSSToResult:
    def parse(self, data, site):        
        items = []
        
        for item in re.findall("<item>(.*?)</item>", data, re.IGNORECASE|re.DOTALL| re.MULTILINE):
            items.append(self.parseItem(item, site))
            
        return items
    
    def parseItem(self, data, site):
        'Parse the data in the items.'        
        title = ParseSimpleStringTag('title', data)
        abstract = ParseSimpleStringTag('description', data)
        url = ParseSimpleStringTag('link', data).replace('&amp;', '&')
        r = Result(title, abstract, site, url)        
        return r
    
class XMLToResult:
    def parse(self, data, site):        
        items = []
        
        for item in re.findall("<rs:RelatedSearchResult>(.*?)</rs:RelatedSearchResult>", data, re.IGNORECASE|re.DOTALL| re.MULTILINE):
            items.append(self.parseItem(item, site))
            
        return items
    
    def parseItem(self, data, site):
        'Parse the data in the items.'        
        title = ParseSimpleStringTag('rs:Title', data)
        abstract = ParseSimpleStringTag('description', data)
        url = ParseSimpleStringTag('rs:Url', data).replace('&amp;', '&')
        r = Result(title, abstract, site, url)        
        return r

class ResultJsonEncoder(simplejson.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Result):
            return {"title": obj.title, "abstract": obj.abstract, "url" : obj.url, "site": obj.site, "id": obj.id}
        return simplejson.JSONEncoder.default(self, obj)
    
class ResultHtmlEncoder():
    def default(self, obj):
        if isinstance(obj, Result):
            return "<li><div><h2><a href=\"" + obj.url +"\">" + obj.title + "</a></h2><p>"+ obj.abstract +"</p></div></li>"
    
    def encode(self, obj):
        data = "";
        for item in obj:
            if item is not None:
                if item.url is None:
                    item.url = ""
                if item.title is None:
                    item.title = ""
                if item.abstract is None:
                    item.abstract = ""
                data = data + "<li><div><h2><a href=\"" + item.url +"\">" + item.title + "</a></h2><p>"+ item.abstract +"</p></div></li>"
        return data
    


class ResultRelatedHtmlEncoder():
    def default(self, obj):
        if isinstance(obj, Result):
            return "<li><a href=\"" + obj.title +"\">" + obj.title + "</a></li>"
    
    def encode(self, obj):
        data = "";
        for item in obj:
            if item is not None:
                if item.url is None:
                    item.url = ""
                if item.title is None:
                    item.title = ""
                if item.abstract is None:
                    item.abstract = ""
                
                data = data + "<li><div><h2><a href=\"/" + item.title +"\">" + item.title + "</a></h2><p>"+ item.abstract +"</p></div></li>"
        return data
    



class Search(webapp.RequestHandler):
    @memoize('subject:subject=%s')
    def getSubject(self, subject):
        return db.Query(Model.SearchTerm).filter("term =", subject).get()
    @memoize('searchProviders')
    def getSearchProviders(self):
        return db.Query(Model.SearchProvider).filter("Category =", 'General' ).fetch(30)
    @memoize('relatedProviders')	
    def getRelatedProviders(self):
        return db.Query(Model.SearchProvider).filter("Category =", 'Related' ).get()
    def get(self, term, provider):
        return db.Query(Model.SearchResult).filter("SearchTerm =",searchTerm).filter("SearchProvider =",prov).get()

    'Searches for the top sites in a topic'
    def get(self, category = "", subject=""):        
        category = urllib.unquote_plus(category)        
        subject = urllib.unquote_plus(subject)
        
        category = self.request.get("category", category)
        subject = self.request.get("subject", subject)
        
        category = urllib.unquote(category)        
        subject = urllib.unquote(subject)
        
        formatter = Url.UrlFormat()
        category = formatter.removeXSS(category)
                
        if subject == "" or subject is None:
            subject = category
            category = ""
        
        if category == "" or category is None:
            category = "General"
                
        cachedSubject = self.getSubject(subject)
        
        if cachedSubject is None:
            cachedSubject = Model.SearchTerm(term = subject)
            cachedSubject.put()
            
        searchProviders = self.getSearchProviders()    
        relatedProvider = self.getRelatedProviders()
        
        midPoint = len(searchProviders) / 2
        
        providers1 = searchProviders[0:midPoint]
        providers2 = searchProviders[midPoint:len(searchProviders)]
        
        parser = RSSToResult()
        encoder = ResultHtmlEncoder()
      
        searchTerm = cachedSubject
        
        currentTime = datetime.datetime.now() - datetime.timedelta(days = 1)
      
        for prov in providers1:
            res = db.Query(Model.SearchResult).filter("SearchTerm =",searchTerm).filter("Last_Accessed >=", currentTime).filter("SearchProvider =",prov).get()
           
            if res is not None:
                prov.TempResult = encoder.encode(parser.parse(res.Result, prov.Name))
                
            prov.HtmlUrl = prov.HtmlUrl.replace('{{query}}', subject)
     
        for prov in providers2:
            res = db.Query(Model.SearchResult).filter("SearchTerm =",searchTerm).filter("Last_Accessed >=", currentTime).filter("SearchProvider =",prov).get()
            
            if res is not None:
                prov.TempResult = encoder.encode(parser.parse(res.Result, prov.Name))
            
            prov.HtmlUrl = prov.HtmlUrl.replace('{{query}}', subject)
            
        #Retrieve the Related Searches
        res = db.Query(Model.SearchResult).filter("SearchTerm =",searchTerm).filter("SearchProvider =", relatedProvider).get()
        if res is not None:
            encoder = ResultRelatedHtmlEncoder()
            parser = XMLToResult()
            relatedProvider.Avail = True
            relatedProvider.TempResult = encoder.encode(parser.parse(res.Result, relatedProvider.Name))
        else:
            relatedProvider.Avail = False
            
        path = os.path.join(os.path.dirname(__file__), 'results.tmpl')
        
        self.response.out.write(template.render(path, {'decoded_query': category, "related": relatedProvider, "decoded_subject": subject, 'query': subject, 'subject': subject , 'urls1': providers1, 'urls2': providers2}))

class SiteSearch(webapp.RequestHandler):
    def get(self, site = "", term = ""):
       
        querysite = urllib.unquote_plus(site)        
        queryterm = urllib.unquote_plus(term)
        
        #'Get the data from the cache if available.'
        searchTerm = db.Query(Model.SearchTerm).filter("term =", queryterm).get()
        provider = db.Query(Model.SearchProvider).filter("Name =", querysite).get()
        
        if provider is None:
            self.error(500)
        
        query = None        
        data = ""
        
        if searchTerm is not None and provider is not None:
            query = db.Query(Model.SearchResult).filter("SearchTerm =",searchTerm).filter("SearchProvider =",provider).get()
        
        currentTime = datetime.datetime.now() - datetime.timedelta(days = 1)
        
        if query is None:
            query = Model.SearchResult()
            
            query.SearchTerm = searchTerm
            query.SearchProvider = provider
            
            url = provider.FeedUrl.replace("{{query}}", term)            
            data = urlfetch.fetch(url).content            
            data = data.decode('utf-8')            
            query.Result = data
            
            query.put()
        else:
            if query.Last_Accessed >= currentTime:
    	        url = provider.FeedUrl.replace("{{query}}", term)            
                data = urlfetch.fetch(url).content            
                data = data.decode('utf-8')            
                query.Result = data
                query.put()

            data = query.Result

        if provider.FeedType == 'RSS':
            parser = RSSToResult()
        else:
            parser = XMLToResult()
            
        encoder = ResultJsonEncoder()

        self.response.out.write(encoder.encode(parser.parse(data, site)))

class Index(webapp.RequestHandler):
    @memoize('recent')
    def getRecentSearches(self):
        return db.Query(Model.SearchTerm).order("-firstQueryDateTime").fetch(10, 0)

    def get(self, action = ""):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        recentSearches = self.getRecentSearches()
        
        for recent in recentSearches:
            recent.clean = urllib.unquote(recent.term)
            
        self.response.out.write(template.render(path, { "recentSearches": recentSearches }))

class SiteMap(webapp.RequestHandler):
    @memoize('sitemap')
    def getSearches(self):
        recentSearches = db.Query(Model.SearchTerm).order("-firstQueryDateTime").fetch(500)
        return recentSearches
		
    def get(self, action = ""):
        path = os.path.join(os.path.dirname(__file__), "sitemapTemplate.xml");
        recentSearches = self.getSearches()
        
        templateOutput = template.render(path, {"terms": recentSearches, "today": datetime.date.today()})
        
        self.response.out.write(templateOutput)

class CleanUp(webapp.RequestHandler):
	def get(self):
		results = db.Query(Model.SearchResult).filter("Added_On <", datetime.datetime.now() - datetime.timedelta(hours = 2) ).fetch(100)		
		db.delete(results)
		
def un_unicode_string(string):
    'strip unicode characters'   
    return unicodedata.normalize('NFKD', unicode(string)).encode('ASCII', 'ignore')

def main():
    application = webapp.WSGIApplication([("/Sitemap.xml", SiteMap),(r'/CleanUp', CleanUp),("/Site/(.*)/(.*)", SiteSearch), ("/(.*)/(.*)", Search), ("/", Index), ("/(index.html)*", Index) ,("/(.*)", Search) ,("/query", Search)], debug=False)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()