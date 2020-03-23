import requests
import json
import io
import ts3
import time

Regions = ["na1","la1","la2","euw1","kr"]
adminClid = 0
messageQueue = []
timeOut = 1

# server group id corresponding to each rank
servergroupsNA = {
    'IRON': 225,
    'BRONZE': 159,
    'SILVER': 160,
    'GOLD': 161,
    'PLATINUM': 162,
    'DIAMOND': 163,
    'MASTER': 226,
    'GRANDMASTER': 227,
    'CHALLENGER':228
}
servergroupsLAN = {
    'IRON': 230,
    'BRONZE': 201,
    'SILVER': 202,
    'GOLD': 203,
    'PLATINUM': 204,
    'DIAMOND': 205,
    'MASTER': 206,
    'GRANDMASTER': 229,
    'CHALLENGER':207
}
rankColors = {
    'IRON': '#6b6b6b',
    'BRONZE': '#9c6e59',
    'SILVER': '#8a8a8a',
    'GOLD': '#ffbc36',
    'PLATINUM': '#00a16e',
    'DIAMOND': '#8d87ff',
    'MASTER': '#cf4ae0',
    'GRANDMASTER': '#e82e6f',
    'CHALLENGER': '#ffcc00'
}
# load authentication variables
with open("auth.json") as authfile:
    authVars = json.load(authfile)
    APIKey = authVars['APIKey']
    host = authVars['host']
    port = authVars['port']
    username = authVars['username']
    password = authVars['password']
    adminUid = authVars['adminuid']

# get summoner data from their name and region
def requestSummonerData(region, summonerName):
    summonerName.replace(" ","%20")
    URL = "https://" + region + ".api.riotgames.com/lol/summoner/v4/summoners/by-name/" + summonerName + "?api_key=" + APIKey
    response = requests.get(URL)
    if response.status_code == 200:
        return response.json()
    else:
        print("Summoner Name: {}, Region: {}, Status Code: {}".format(summonerName, region, response.status_code))
        return response.status_code

# get a summoners ranked data based on their ID and region
def requestRankedData(region, ID):
    URL = "https://"+region+".api.riotgames.com/lol/league/v4/entries/by-summoner/" + ID + "?api_key=" + APIKey
    response = requests.get(URL)
    if response.status_code == 200:
        return response.json()
    else:
        print("Summoner ID: {}, Region: {}, Status Code: {}".format(ID, region, response.status_code))
        return response.status_code

def getUserRank(cldbid):
    rankedData = ""
    with open('userdata.json') as userfile:
        users = json.load(userfile)
    user = users[cldbid]
    summonerID = user['summonerId']
    region = Regions[int(user['region'])]
    if summonerID:
        rankedData = requestRankedData(region, summonerID)
        rankedData.sort(key=lambda k: k['queueType'], reverse=True)
    return region, rankedData

# assign groups to a user identified by their cldbid (client database ID)
def assignGroup(cldbid,ts3conn):

    # if the user doesnt exist prompts a message to register the user
    try:
        region, rankedData = getUserRank(cldbid)
    except KeyError:
        #if the admin is online send a text message if not then send an offline message
        if adminClid:
            ts3conn.exec_("sendtextmessage", targetmode=1, target=adminClid, msg="User "+ cldbid +" isn't registered!")
        else:
            ts3conn.exec_("messageadd", cluid=adminUid, subject="New User", message="User "+ cldbid +" isn't registered!")
        return
    except AttributeError:
        return
    
    if rankedData:

        # only give ranks to people who have ranked data some people are unranked
        try:
            rank = rankedData[0]['tier']
        except KeyError:
            return
        except IndexError:
            return

        # get the servergroup corresponding to thier rank
        if region == "na1":
            servergroup = str(servergroupsNA[rank])
        else:
            servergroup = str(servergroupsLAN[rank])

        # teamspeak query command to give a rank to a client
        try:
            ts3conn.exec_("servergroupaddclient", sgid=servergroup, cldbid=cldbid)
            print("servergroup: " + rank)
        except ts3.query.TS3QueryError:
            pass

#register a user to the database
def registerUser(message):
   
    splitinfo = command, cldbid, region, summonerName = message.split(" ", 3)

    # request league id from name and region if they play league
    if summonerName == "none":
        ID = ""
    else:
        ID = requestSummonerData(Regions[int(region)], summonerName)['id']

    # get user list
    with open('userdata.json') as userfile:
        users = json.load(userfile)
    users[cldbid]={'summonerId': ID, 'region': region}

    # add user to list
    with open('userdata.json', 'w') as userfile:
        json.dump(users, userfile, sort_keys=True, indent=2)
    
    return cldbid

def delUser(message):

    splitinfo = command, cldbid = message.split(" ")

    with open('userdata.json') as userfile:
        users = json.load(userfile)
    del users[cldbid]

    # add user to list
    with open('userdata.json', 'w') as userfile:
        json.dump(users, userfile, sort_keys=True, indent=2)

def formatRankMessage(rankedData):
    message = ""
    for queue in rankedData:
        queueType = queue['queueType']
        tier = queue['tier'].lower().capitalize()
        rank = queue['rank']
        lp = queue['leaguePoints']
        wins = queue['wins']
        losses = queue['losses']
        total = wins + losses
        winrate = round((wins / total) * 100)
        if queueType == "RANKED_FLEX_SR":
            queueType = "Flex Queue"
        if  queueType == "RANKED_SOLO_5x5":
            queueType = "Solo/Duo Queue"
        message += "\n"
        rankedColor = rankColors[queue['tier']]
        message += "\n[B]{}:[/B] [color={}]{}[/color] {} {} lp".format(queueType, rankedColor, tier, rank, lp)
        message += "\n[B][color=#4287f5]Wins:[/color][/B] {}".format(wins)
        message += "\n[B][color=#f54242]Losses:[/color][/B] {}".format(losses)
        message += "\n[B]Total Games:[/B] {}".format(total)
        message += "\n[B]Winrate:[/B] {}%".format(winrate)
    return message

# start of program connect the bot to the teamspeak server
# and set up the bot to receive server and text updates
with ts3.query.TS3ServerConnection("telnet://" + username + ":" + password + "@" + host + ":" + port) as ts3conn:
    
    ts3conn.exec_("use", sid=4)
    botClid = ts3conn.exec_("whoami")[0]['client_id']
    ts3conn.exec_("clientmove", clid=botClid, cid=235)
    ts3conn.exec_("servernotifyregister", event="server")
    ts3conn.exec_("servernotifyregister", event="textprivate")

    clients = ts3conn.query("clientlist").all()
    cldbids = [client["client_database_id"] for client in clients if client["client_type"] != "1"]
    for cldbid in cldbids:
        assignGroup(cldbid, ts3conn)
    del clients
    del cldbids

    # always listening to the teamspeak notifcations
    while True:
        ts3conn.send_keepalive()

        try:
            event = ts3conn.wait_for_event(timeout=200)
        except ts3.query.TS3TimeoutError:
            pass
        else:
            eventType = event.event

            #on user connection
            if eventType == "notifycliententerview":

                eventData = event.parsed[0]
                print(event.data)
                cluid = eventData['client_unique_identifier']

                if cluid == adminUid:
                    adminClid = eventData['clid']

                # get users cldbid (client database id) from cluid
                resp = ts3conn.exec_("clientgetdbidfromuid", cluid=cluid)
                cldbid = resp[0]['cldbid']
                assignGroup(cldbid, ts3conn)

            if eventType == "notifytextmessage":
                
                eventData = event.parsed[0]
                print(event.data)
                message = eventData['msg']
                invokeruid = eventData['invokeruid']
                invokerid = eventData['invokerid']
                if invokerid == botClid:
                    continue
                for messageInfo in messageQueue:
                    timeSince = time.time() - messageInfo[1]
                    if timeSince > messageInfo[2]:
                        messageQueue.remove(messageInfo)
                for messageInfo in messageQueue:
                    if messageInfo[0] == invokerid:
                        try:
                            ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="Timeout of " + str(round(messageInfo[2]-timeSince, 1)) \
                                + " seconds! Please do not spam!")
                        except ts3.query.TS3QueryError:
                            pass
                        if messageInfo[3]%5 == 0:
                            messageInfo[2] = messageInfo[2] * 10
                        if messageInfo[3] >= 15:
                            if messageInfo[3] >= 30:
                                try:
                                    ts3conn.exec_("banclient", clid=invokerid, time=3600, banreason="Spam!")
                                except ts3.query.TS3QueryError:
                                    pass
                            try:
                                ts3conn.exec_("clientkick", clid=invokerid, reasonid=5, reasonmsg="Spam!")
                            except ts3.query.TS3QueryError:
                                pass
                        messageInfo[3] += 1
                        break
                        
                else:
                    timeOfMessage = time.time()
                    messageInfo = [invokerid, timeOfMessage, timeOut, 1]
                    messageQueue.append(messageInfo)

                    if message.startswith("!register"):
                        if invokeruid == adminUid:
                            cldbid = registerUser(message)
                            assignGroup(cldbid, ts3conn)
                            ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="User has been registered!")

                    if message.startswith("!deluser"):
                        if invokeruid == adminUid:
                            delUser(message)
                            ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="User has been deleted!")

                    if message.startswith("!rank"):
                        if message == "!rank":
                            resp = ts3conn.exec_("clientgetdbidfromuid", cluid=invokeruid)
                            cldbid = resp[0]['cldbid']
                            try:
                                region, rankedData = getUserRank(cldbid)
                                if rankedData:
                                    reply = formatRankMessage(rankedData)
                                    ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg=reply)
                                else:
                                    ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="Apparently you dont play league. If this is false, " + \
                                                                                                                    " message the owner  to get it fixed!")
                            except KeyError:
                                ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="You are not registered! Message the owner to register!")
                        else:
                            try:
                                command, region, summonerName = message.split(" ", 2)
                                ID = requestSummonerData(Regions[int(region)], summonerName)['id']
                            except IndexError:
                                ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="Region parameter has to be an valid integer that corresponds to a region.")
                                continue
                            except ValueError:
                                ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="Incorrect Format, Expected !rank <region> <summonerName>")
                                continue
                            except TypeError:
                                ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="The summoner you have requested doesn't exist in this region.")
                                continue

                            rankedData = requestRankedData(Regions[int(region)], ID)
                            if rankedData:
                                    reply = formatRankMessage(rankedData)
                                    ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg=reply)
                            else:
                                ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="This user is unranked.")
            # if admin leaves the server set adminclid to 0 so offline messages are sent
            if eventType == "notifyclientleftview":
                eventData = event.parsed[0]
                print(event.data)
                clid = eventData['clid']
                if (clid == adminClid):
                    adminClid = 0