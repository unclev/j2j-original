# Part of J2J (http://JRuDevels.org)
# Copyright 2008 JRuDevels.org

class config:

    def __init__(self, configname=["j2j.conf","~/.j2j/j2j.conf","/etc/j2j/j2j.conf"]):
        import ConfigParser
        config=ConfigParser.ConfigParser()
        config.read(configname)
        self.JID=unicode(config.get("component","JID"),"utf-8")
        self.HOST=unicode(config.get("component","Host"),"utf-8")
        self.PORT=unicode(config.get("component","Port"),"utf-8")
        self.PASSWORD=unicode(config.get("component","Password"),"utf-8")

        self.DB_HOST=unicode(config.get("database","Host"),"utf-8")
        self.DB_TYPE=unicode(config.get("database","Type"),"utf-8")
        self.DB_USER=unicode(config.get("database","User"),"utf-8")
        self.DB_NAME=unicode(config.get("database","Name"),"utf-8")
        self.DB_PASS=unicode(config.get("database","Password"),"utf-8")
        self.DB_PREFIX=unicode(config.get("database","Prefix"),"utf-8")

        admins=unicode(config.get("admins","List"),"utf-8")
        self.ADMINS=admins.split(",")