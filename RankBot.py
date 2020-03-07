import requests
import json
import io
import ts3

Regions = ["na1","la1","la2","euw1"]
adminClid = 0

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

# load authentication variables
with open("auth.json") as authfile:
    authVars = json.load(authfile)
    APIKey = authVars['APIKey']
    password = authVars['password']
    host = authVars['host']
    port = authVars['port']
    adminUid = authVars['adminuid']

# get summoner data from their name and region
def requestSummonerData(region, summonerName):
    URL = "https://" + region + ".api.riotgames.com/lol/summoner/v4/summoners/by-name/" + summonerName + "?api_key=" + APIKey
    response = requests.get(URL)
    return response.json()

# get a summoners ranked data based on their ID and region
def requestRankedData(region, ID):
    URL = "https://"+region+".api.riotgames.com/lol/league/v4/entries/by-summoner/" + ID + "?api_key=" + APIKey
    response = requests.get(URL)
    return response.json()

# assign groups to a user identified by their cldbid (client database ID)
def assignGroup(cldbid,ts3conn):

    # loads user json
    with open('userdata.json') as userfile:
        users = json.load(userfile)

    # if the user doesnt exist prompts a message to register the user
    try:
        user = users[cldbid]
    except KeyError:
        #if the admin is online send a text message if not then send an offline message
        if adminClid:
            ts3conn.exec_("sendtextmessage", targetmode=1, target=adminClid, msg="User "+ cldbid +" isn't registered!")
        else:
            ts3conn.exec_("messageadd", cluid=adminUid, subject="New User", message="User "+ cldbid +" isn't registered!")
        return

    # gets a user's ranked info and assigns them the correct rank
    summonerID = user['summonerId']

    # some users dont play league
    if summonerID:

        region = Regions[int(user['region'])]
        rankeddata = requestRankedData(region, summonerID)

        # only give ranks to people who have ranked data
        # some people are unranked
        try:
            rank = rankeddata[-1]['tier']
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
        except ts3.query.TS3QueryError:
            pass


#register a user to the database
def registerUser(message, invokeruid):
   
    splitinfo = message.split(" ", 3)
    cldbid = splitinfo[1]
    region = splitinfo[2]
    summonerName = splitinfo[3].replace(" ", "%20")

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

# start of program connect the bot to the teamspeak server
# and set up the bot to receive server and text updates
with ts3.query.TS3ServerConnection("telnet://RankBot:" + password + "@" + host + ":" + port) as ts3conn:
    
    ts3conn.exec_("use", sid=4)
    ts3conn.exec_("servernotifyregister", event="server")
    ts3conn.exec_("servernotifyregister", event="textprivate")
    
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

                if message.startswith("!register"):
                    if invokeruid == adminUid:
                        cldbid = registerUser(message, invokeruid)
                        assignGroup(cldbid, ts3conn)

                if message.startswith("!rank"):
                    resp = ts3conn.exec_("clientgetdbidfromuid", cluid=invokeruid)
                    cldbid = resp[0]['cldbid']
                    with open('userdata.json') as userfile:
                        users = json.load(userfile)
                        try:
                            user = users[cldbid]
                            summonerID = user['summonerId']
                            if summonerID:
                                region = Regions[int(user['region'])]
                                rankeddata = requestRankedData(region, summonerID)
                                rankeddata = reversed(rankeddata)
                                for queue in rankeddata:
                                    queueType = queue['queueType']
                                    tier = queue['tier'].lower().capitalize()
                                    rank = queue['rank']
                                    lp = queue['leaguePoints']
                                    if queueType == "RANKED_FLEX_SR":
                                        queueType = "Flex Queue"
                                    if  queueType == "RANKED_SOLO_5x5":
                                        queueType = "Solo/Duo Queue"
                                    ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg=queueType + ": " + tier + " " + rank + " " + str(lp) + " lp")
                            else:
                                ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="Apparently you dont play league. If this is false " + \
                                                                                                                " message the owner  to get it fixed!")
                        except KeyError:
                            ts3conn.exec_("sendtextmessage", targetmode=1, target=invokerid, msg="You are not registered! Message the owner to register!")
        
            # if admin leaves the server set adminclid to 0 so offline messages are sent
            if eventType == "notifyclientleftview":
                eventData = event.parsed[0]
                print(event.data)
                clid = eventData['clid']
                if (clid == adminClid):
                    adminClid = 0