# Part of J2J (http://JRuDevels.org)
# Copyright 2008 JRuDevels.org

__id__ = "$Id$"

from ConfigParser import NoOptionError, NoSectionError

import ConfigParser
import os

def config_decorator(func):
    def wrapper(section, option, default=None, required=False):
        try:
            v = func(section, option)
        except (NoOptionError, NoSectionError):
            if required:
                raise
            v = default
        if isinstance(v, str):
            v = v.decode('utf-8')
        return v
    return wrapper


class Config:

    def __init__(self, configname=["j2j.conf",
                                   os.path.expanduser("~/.j2j/j2j.conf"),
                                   "/etc/j2j/j2j.conf"]):
        config = ConfigParser.ConfigParser()
        config.read(configname)

        get = config_decorator(config.get)
        getboolean = config_decorator(config.getboolean)

        self.JID = get("component", "JID", required=True)
        self.HOST = get("component", "Host", required=True)
        self.PORT = get("component", "Port", required=True)
        self.PASSWORD = get("component", "Password", required=True)
        self.SEND_PROBES = getboolean("component", "Send_probes", default=True)
        
        self.PROCESS_PID = get("process", "Pid")

        self.DB_HOST = get("database", "Host")
        if self.DB_HOST == "":
            self.DB_HOST = None
        self.DB_TYPE = get("database", "Type", required=True)
        self.DB_USER = get("database", "User", required=True)
        self.DB_NAME = get("database", "Name", required=True)
        self.DB_PASS = get("database", "Password", required=True)
        self.DB_PREFIX = get("database", "Prefix", default='j2j_')

        self.DEBUG_REGISTRATIONS = getboolean("debug", "registrations",
                                              default=False)
        self.DEBUG_LOGINS = getboolean("debug", "logins", default=False)
        self.LOGFILE = None
        if self.DEBUG_REGISTRATIONS or self.DEBUG_LOGINS:
            self.LOGFILE = get("debug", "logfile", required=True)

        self.DEBUG_COMPXML = getboolean("debug", "component_xml",
                                        default=False)
        self.DEBUG_CLXML = getboolean("debug", "clients_xml", default=False)
        self.DEBUG_CLXMLACL = get("debug", "clients_jids_to_log", default='')
        self.DEBUG_XMLLOG = None
        if self.DEBUG_COMPXML or self.DEBUG_CLXML:
            self.DEBUG_XMLLOG = get("debug", "xml_logging", required=True)

        admins = get("admins", "List", default="")
        self.ADMINS = admins.split(",")
        self.REGISTRATION_NOTIFY = getboolean("admins",
                                              "Registrations_notify",
                                              default=True)
