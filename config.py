# Part of J2J (http://JRuDevels.org)
# Copyright 2008 JRuDevels.org

__id__ = "$Id$"

from ConfigParser import NoOptionError

import ConfigParser
import os

class Config:

    def __init__(self, configname=["j2j.conf",os.path.expanduser("~/.j2j/j2j.conf"),"/etc/j2j/j2j.conf"]):
        config=ConfigParser.ConfigParser()
        config.read(configname)
        self.JID=unicode(config.get("component","JID"),"utf-8")
        self.HOST=unicode(config.get("component","Host"),"utf-8")
        self.PORT=unicode(config.get("component","Port"),"utf-8")
        self.PASSWORD=unicode(config.get("component","Password"),"utf-8")
        try:
            self.SEND_PROBES = config.getboolean("component", "Send_probes")
        except NoOptionError:
            self.SEND_PROBES = True
        
        self.PROCESS_PID=unicode(config.get("process","Pid"),"utf-8")

        self.DB_HOST=unicode(config.get("database","Host"),"utf-8")
        if self.DB_HOST=="":
            self.DB_HOST=None
        self.DB_TYPE=unicode(config.get("database","Type"),"utf-8")
        self.DB_USER=unicode(config.get("database","User"),"utf-8")
        self.DB_NAME=unicode(config.get("database","Name"),"utf-8")
        self.DB_PASS=unicode(config.get("database","Password"),"utf-8")
        self.DB_PREFIX=unicode(config.get("database","Prefix"),"utf-8")

        self.LOGFILE=config.get("debug","logfile")
        self.DEBUG_REGISTRATIONS=config.getboolean("debug","registrations")
        self.DEBUG_LOGINS=config.getboolean("debug","logins")
        self.DEBUG_XMLLOG=config.get("debug","xml_logging")
        self.DEBUG_COMPXML=config.getboolean("debug","component_xml")
        self.DEBUG_CLXML=config.getboolean("debug","clients_xml")
        self.DEBUG_CLXMLACL=config.get("debug","clients_jids_to_log")

        admins=unicode(config.get("admins","List"),"utf-8")
        self.ADMINS=admins.split(",")
        self.REGISTRATION_NOTIFY = config.getboolean("admins", "Registrations_notify")
