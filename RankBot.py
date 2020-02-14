import requests
import json
import telnetlib
import time
import io

Regions = ["na1","la1","la2"]

Host = "127.0.0.1"
Port = "10011"

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

with open("auth.txt") as authfile:
    authVars = json.load(authfile)
    APIKey = authVars['APIKey']
    password = authVars['password']
    
def requestSummonerData(region, summonerName):
    URL = "https://" + region + ".api.riotgames.com/lol/summoner/v4/summoners/by-name/" + summonerName + "?api_key=" + APIKey
    response = requests.get(URL)
    return response.json()

def requestRankedData(region, ID):
    URL = "https://"+region+".api.riotgames.com/lol/league/v4/entries/by-summoner/" + ID + "?api_key=" + APIKey
    response = requests.get(URL)
    return response.json()

def assignGroup(cldbid,telnet):

    with open('userdata.txt') as userfile:
        users = json.load(userfile)

    try:
        user = users[cldbid]
    except KeyError:
        command = "sendtextmessage targetmode=1 target=397 msg=User\s"+ cldbid +"\sisn't\sregistered!\n"
        telnet.write(command.encode('ascii'))
        return

    summonerID = user['summonerId']

    if summonerID:
        region = Regions[int(user['region'])]
        rankeddata = requestRankedData(region, summonerID)

        try:
            rank = rankeddata[0]['tier']
        except KeyError:
            return
        except IndexError:
            return

        if region == "na1":
            servergroup = str(servergroupsNA[rank])
        else:
            servergroup = str(servergroupsLAN[rank])

        addgroupcommand = "servergroupaddclient sgid=" + servergroup + " cldbid=" + cldbid + "\n"
        telnet.write(addgroupcommand.encode('ascii'))

telnet = telnetlib.Telnet()
telnet.open(Host, Port)
telnet.write(("login serveradmin " + password + "\n").encode('ascii'))
telnet.write("use 4\n".encode('ascii'))
telnet.write("clientupdate client_nickname=RankBot\n".encode('ascii'))
telnet.write("servernotifyregister event=server\n".encode('ascii'))
telnet.write("servernotifyregister event=textprivate\n".encode('ascii'))

i = 0
while 1:
    readData = telnet.read_very_eager()
    readData = readData.decode("utf-8")
    lines = readData.splitlines()
    lines = filter(None,lines)
    for line in lines:
        print(line)
        if line.startswith("notifycliententerview"):

            cluidstart = line.index("client_unique_identifier")+25
            cluidend = line.index(" ",cluidstart)
            cluid = line[cluidstart:cluidend]

            telnet.write(("clientgetdbidfromuid cluid=" + cluid + "\n").encode('ascii'))

        if line.startswith("cluid"):
            
            cldbidstart = line.index("cldbid")+7
            cldbid = line[cldbidstart:]

            assignGroup(cldbid, telnet)

        if line.startswith("notifytextmessage targetmode=1 msg=!register"):

            startindex = line.index("!register")+11
            endindex = line.index(" ", startindex)
            registerdata = line[startindex:endindex]
            splitinfo = registerdata.split("\s", 2)
            cldbid = splitinfo[0]
            region = splitinfo[1]
            name = splitinfo[2].replace("\\s", "%20")
            ID = requestSummonerData(Regions[int(region)], name)['id']

            with open('userdata.txt') as userfile:
                users = json.load(userfile)
            users[cldbid]={"summonerId": ID, "region": region}

            with open('userdata.txt', 'w') as userfile:
                json.dump(users, userfile)
            
            assignGroup(cldbid, telnet)

    time.sleep(0.5)
    if i == 300:
        telnet.write("whoami\n".encode('ascii'))
        i=0
    i = i+1
telnet.close()