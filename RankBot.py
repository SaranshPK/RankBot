import requests
import json
import telnetlib
import time
import io

Regions = ["na1","la1","la2","euw1"]
Port = "10011"
adminClid = 0

# server group id corresponding to each rank
servergroupsNA = {
    "IRON": 225,
    "BRONZE": 159,
    "SILVER": 160,
    "GOLD": 161,
    "PLATINUM": 162,
    "DIAMOND": 163,
    "MASTER": 226,
    "GRANDMASTER": 227,
    "CHALLENGER":228
}
servergroupsLAN = {
    "IRON": 230,
    "BRONZE": 201,
    "SILVER": 202,
    "GOLD": 203,
    "PLATINUM": 204,
    "DIAMOND": 205,
    "MASTER": 206,
    "GRANDMASTER": 229,
    "CHALLENGER":207
}

# load authentication variables
with open("auth.txt") as authfile:
    authVars = json.load(authfile)
    APIKey = authVars['APIKey']
    password = authVars['password']
    Host = authVars["host"]
    adminUid = authVars["adminuid"]

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
def assignGroup(cldbid,telnet):

    # loads user json
    with open('userdata.txt') as userfile:
        users = json.load(userfile)

    # if the user doesnt exist prompts a message to register the user
    try:
        user = users[cldbid]
    except KeyError:

        #if the admin is online send a text message if not then send an offline message
        if adminClid:
            command = "sendtextmessage targetmode=1 target=" + adminClid + " msg=User\s"+ cldbid +"\sisn't\sregistered!\n"
            
        else:
            command = "messageadd cluid=" + adminUid + " subject=New\sUser message=User\s"+ cldbid +"\sisn't\sregistered!\n"

        telnet.write(command.encode('ascii'))
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
        addgroupcommand = "servergroupaddclient sgid=" + servergroup + " cldbid=" + cldbid + "\n"
        telnet.write(addgroupcommand.encode('ascii'))

# start of program connect the bot to the teamspeak server
# and set up the bot to receive server and text updates
telnet = telnetlib.Telnet()
telnet.open(Host, Port)
telnet.write(("login serveradmin " + password + "\n").encode('ascii'))
telnet.write("use 4\n".encode('ascii'))
telnet.write("clientupdate client_nickname=RankBot\n".encode('ascii'))
telnet.write("servernotifyregister event=server\n".encode('ascii'))
telnet.write("servernotifyregister event=textprivate\n".encode('ascii'))

# counter
i = 0

# always listening to the teamspeak notifcations
while 1:

    # read and filter server output
    readData = telnet.read_very_eager()
    readData = readData.decode("utf-8")
    lines = readData.splitlines()
    lines = filter(None,lines)
    for line in lines:

        # logs server messages
        print(line)

        # on user connection
        if line.startswith("notifycliententerview"):

            # get their cluid (client unique id)
            cluidstart = line.index("client_unique_identifier")+25
            cluidend = line.index(" ",cluidstart)
            cluid = line[cluidstart:cluidend]

            if cluid == adminUid:
                
                # get admin clid for text messages
                clidstart = line.index("clid")+5
                clidend = line.index(" ",clidstart)
                adminClid = line[clidstart:clidend]

            # request their cldbid (client database id)
            telnet.write(("clientgetdbidfromuid cluid=" + cluid + "\n").encode('ascii'))

        # upon receiving a clients cldbid
        if line.startswith("cluid"):
            
            cldbidstart = line.index("cldbid")+7
            cldbid = line[cldbidstart:]

            # assign server group corresponding to league rank
            assignGroup(cldbid, telnet)

        # upon receiving !register command
        if line.startswith("notifytextmessage targetmode=1 msg=!register"):

            # parse data from command
            startindex = line.index("!register")+11
            endindex = line.index(" ", startindex)
            registerdata = line[startindex:endindex]
            splitinfo = registerdata.split("\s", 2)
            cldbid = splitinfo[0]
            region = splitinfo[1]
            summonerName = splitinfo[2].replace("\\s", "%20")

            # request league id from name and region if they play league
            if(summonerName == "none"):
                ID = ""
            else:
                ID = requestSummonerData(Regions[int(region)], summonerName)['id']

            # get user list
            with open('userdata.txt') as userfile:
                users = json.load(userfile)
            users[cldbid]={"summonerId": ID, "region": region}

            # add user to list
            with open('userdata.txt', 'w') as userfile:
                json.dump(users, userfile)
            
            # assign server group corresponding to league rank
            assignGroup(cldbid, telnet)
        
        # if admin leaves the server set adminclid to 0
        if line.startswith("notifyclientleftview"):

            clidstart = line.index("clid")+5
            if (line[clidstart:] == adminClid):
                adminClid = 0


    # sleep for half a second before each read
    time.sleep(0.5)

    # send a useless command so teamspeak connection doesnt time out
    if i == 300:
        telnet.write("whoami\n".encode('ascii'))
        i=0
    i = i+1