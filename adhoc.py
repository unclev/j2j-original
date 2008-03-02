# Part of J2J (http://JRuDevels.org)
# Copyright 2007 JRuDevels.org

import utils
import time
from twisted.words.xish.domish import Element
from twisted.words.xish import xpath

__id__ = "$Id$"

class adHoc:
    def __init__(self,component):
        self.commands={"stat": ["Statistics",self.getStat,None,False],\
                       "options": ["Options",self.getOpts,self.setOpts,True],\
                       "replicate_vCard": ["Replicate host's vCard to guest's account",self.getReplica,self.setReplica,True]}
        self.sid=0
        self.vCardSids={}

        self.component=component
        self.config=component.config

    def getSid(self):
        ret=time.strftime("%Y%m%dT%H%M%S",time.localtime(time.time()))+"-"+str(self.sid)
        self.sid+=1
        return ret

    def getCommandsList(self,query):
        for commandNode in self.commands.keys():
            utils.addDiscoItem(query,self.config.JID,self.commands[commandNode][0],commandNode)

    def onCommand(self,el,fro,ID,node):
        sid=el.getAttribute('sessionid')
        action=el.getAttribute('action')
        if not node in self.commands.keys(): return False

        iq=Element((None,"iq"))
        iq.attributes["to"]=fro.full()
        iq.attributes["from"]=self.config.JID
        iq.attributes["id"]=ID
        iq.attributes["type"]="result"

        if action=='execute' or action==None and sid==None:
            self.commands[node][1](iq,fro,ID)

        if action=='cancel':
            command=utils.createCommand(iq,node,"canceled",sid)
            self.component.send(iq)

        if action=='complete' or (sid!=None and action==None) and self.commands[node][2]!=None:
            self.commands[node][2](el,iq,sid,fro,ID)

    def getReplica(self,iq,fro,ID):
        if not fro.full() in self.component.clients.keys():
            command=utils.createCommand(iq,"stat","completed",self.getSid())
            form=utils.createForm(command,"result")
            utils.addTitle(form,"Execution error")
            utils.addLabel(form,"Please log in first.")
            self.component.send(iq)
            return
        command=utils.createCommand(iq,"replicate_vCard","executing",self.getSid())
        form=utils.createForm(command,"form")
        utils.addTitle(form,"vCard replication")
        utils.addLabel(form,"Are you sure want to replicate your host's vCard to your guest's account?")
        utils.addCheckBox(form,"commit_cb","Yes, do it",False)
        self.component.send(iq)

    def setReplica(self,el,iq,sid,fro,ID):
        uid=self.component.db.getIdByJid(fro.userhost())
        if not uid:
            return
        xPathStr='/command/x[@xmlns="jabber:x:data"]'
        commited=xpath.XPathQuery(xPathStr+"/field[@var='commit_cb']/value").queryForString(el)
        if commited=="0" or not fro.full() in self.component.clients.keys():
            command=utils.createCommand(iq,"replicate_vCard","completed",sid)
            form=utils.createForm(command,"result")
            utils.addTitle(form,"Execution canceled")
            utils.addLabel(form,"Replication cancelled")
            self.component.send(iq)
            return
        el = Element((None, "iq"))
        el.attributes["to"]=fro.userhost()
        el.attributes["from"]=self.config.JID
        el.attributes["id"]=sid
        el.attributes["type"]="get"
        vc=el.addElement("vCard")
        vc.attributes["xmlns"]="vcard-temp"
        self.component.send(el)
        self.vCardSids[sid]=(fro,ID)

    def getStat(self,iq,fro,ID):
        command=utils.createCommand(iq,"stat","completed",self.getSid())
        form=utils.createForm(command,"result")
        utils.addTitle(form,"J2J Statistics")
        utils.addLabel(form,"J2J Statistics")
        utils.addLabel(form,"Online Users: "+str(len(self.component.clients.keys())))
        utils.addLabel(form,"Total Users: "+str(self.component.db.getCount("users")))
        utils.addLabel(form,"Version: "+self.component.VERSION)
        upInSecs=int(time.time()-self.component.startTime)
        upInDays=int(upInSecs/(3600*24))
        upInHours=int((upInSecs-upInDays*3600*24)/3600)
        upInMinutes=int((upInSecs-upInDays*3600*24-upInHours*3600)/60)
        upInSecs=int(upInSecs-upInDays*3600*24-upInHours*3600-upInMinutes*60)
        utils.addLabel(form,"Uptime: %d days %d hours %d minutes %d seconds" % (upInDays,upInHours,upInMinutes,upInSecs))
        self.component.send(iq)

    def getOpts(self,iq,fro,ID):
        uid=self.component.db.getIdByJid(fro.userhost())
        if not uid:
            return
        opts=self.component.db.getOptsById(uid)
        gtalk=False
        if fro.full() in self.component.clients.keys():
            gtalk=self.component.clients[fro.full()].isGTalk
        command=utils.createCommand(iq,"options","executing",self.getSid())
        form=utils.createForm(command,"form")
        utils.addTitle(form,"J2J Options and Settings")
        utils.addCheckBox(form,"onlyRoster","Receive messages only from contacts from Guest roster",opts[3])
        if gtalk:
            utils.addLabel(form,"GTalk's Settings:")
            utils.addCheckBox(form,"lightNotify","Light first mail-notify",opts[1])
        utils.addLabel(form,"Auto Reply Settings")
        utils.addCheckBox(form,"autoReplyEnabled","Enable Auto Reply for ALL guest contacts",opts[4])
        utils.addCheckBox(form,"autoReplyButForward","Always forward messages to me",opts[2])
        utils.addMemo(form,"replyText","Text for Auto Reply (1000 chars max)",opts[0])
        self.component.send(iq)

    def setOpts(self,el,iq,sid,fro,ID):
        uid=self.component.db.getIdByJid(fro.userhost())
        if not uid:
            return
        opts=self.component.db.getOptsById(uid)
        command=utils.createCommand(iq,"options","completed",sid)
        xPathStr='/command/x[@xmlns="jabber:x:data"]'
        onlyRoster=xpath.XPathQuery(xPathStr+"/field[@var='onlyRoster']/value").queryForString(el)
        if onlyRoster:
            opts[3]=utils.strToBool(onlyRoster)
        autoReplyEnabled=xpath.XPathQuery(xPathStr+"/field[@var='autoReplyEnabled']/value").queryForString(el)
        if autoReplyEnabled:
            opts[4]=utils.strToBool(autoReplyEnabled)
        autoReplyButForward=xpath.XPathQuery(xPathStr+"/field[@var='autoReplyButForward']/value").queryForString(el)
        if autoReplyButForward:
            opts[2]=utils.strToBool(autoReplyButForward)
        lightNotify=xpath.XPathQuery(xPathStr+"/field[@var='lightNotify']/value").queryForString(el)
        if lightNotify:
            opts[1]=utils.strToBool(lightNotify)
        replyText=xpath.XPathQuery(xPathStr+"/field[@var='replyText']/value").queryForStringList(el)
        if replyText:
            rT=''
            for r in replyText:
                rT=rT+r+"\n"
            rT=rT[:-1]
            rT=rT[:1000]
            opts[0]=rT
        self.component.db.execute("UPDATE %s SET onlyroster='%s', autoreplyenabled='%s', autoreplybutforward='%s', replytext='%s', lightnotify='%s' WHERE id='%s'" % (self.component.db.dbTablePrefix+"users_options",str(opts[3]),str(opts[4]),str(opts[2]),self.component.db.dbQuote(opts[0]),str(opts[1]),str(uid)))
        self.component.db.commit()
        self.component.send(iq)