def webapp_add_wsgi_middleware(app):
  #from google.appengine.ext.appstats import recording
  #app = recording.appstats_wsgi_middleware(app)
  return app
  
remoteapi_CUSTOM_ENVIRONMENT_AUTHENTICATION = (
    'HTTP_X_APPENGINE_INBOUND_APPID', ['literumble'])
