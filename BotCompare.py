#!/usr/bin/env python
import base64
import io
import logging
import time
from operator import attrgetter

import numpy
from PIL import Image
from flask import request
from google.appengine.api import memcache

import structures
from structures import load_blob


def bot_compare():
    global_dict = {}
    starttime = time.time()
    query = request.query_string.decode('utf-8').replace("%20", " ").replace("+", " ")
    parts = query.split("&")
    requests = {}
    if parts[0] != "":
        for pair in parts:
            ab = pair.split('=', 1)
            requests[ab[0]] = ab[1] if len(ab) > 1 else ""

    game = requests.get("game")
    if game is None:
        return "ERROR: RUMBLE NOT SPECIFIED IN FORMAT game=____"

    botaName = requests.get("bota", None)
    if botaName is None:
        return "ERROR: BOT_A NOT SPECIFIED IN FORMAT bota=____"

    botbName = requests.get("botb", None)
    if botbName is None:
        return "ERROR: BOT_B NOT SPECIFIED IN FORMAT botb=____"

    lim = int(requests.get("limit", "10000000"))
    order = requests.get("order", None)
    timing = bool(requests.get("timing", False))
    dark = requests.get("theme", "") == "dark"

    extraArgs = ""
    if timing:
        extraArgs += "&amp;timing=1"
    if dark:
        extraArgs += "&amp;theme=dark"
    reverseSort = True

    if order is None or order == "" or order.replace(" ", "") == "":
        order = "Name"
        reverseSort = False
    elif order[0] == "-":
        order = order[1:]
        reverseSort = False

    if order == "Latest Battle":
        order = "LastUpload"

    parsetime = time.time() - starttime

    cached = True
    keyhasha = botaName + "|" + game
    bota = memcache.get(keyhasha)
    if bota is None:
        bota = global_dict.get(keyhasha, None)
    else:
        global_dict[keyhasha] = bota

    if bota is None or bota.PairingsList is None:
        bota = structures.BotEntry.get_by_key_name(keyhasha)

        if bota is not None:
            memcache.set(keyhasha, bota)
            global_dict[keyhasha] = bota
            cached = False

    if bota is None:
        return "ERROR. name/game combination does not exist: " + botaName + "/" + game

    keyhashb = botbName + "|" + game
    botb = memcache.get(keyhashb)
    if botb is None:
        botb = global_dict.get(keyhashb, None)
    else:
        global_dict[keyhashb] = botb

    if botb is None or botb.PairingsList is None:
        botb = structures.BotEntry.get_by_key_name(keyhashb)
        if botb is not None:
            memcache.set(keyhashb, botb)
            global_dict[keyhashb] = botb
            cached = False

    if botb is None:
        return "ERROR. name/game combination does not exist: " + botbName + "/" + game

    rumble = global_dict.get(game, None)
    if rumble is None:
        rumble = memcache.get(game)
        if rumble is None:
            rumble = structures.Rumble.get_by_key_name(game)
            if rumble is None:
                return "RUMBLE NOT FOUND"
            else:
                global_dict[game] = rumble
                memcache.set(game, rumble)
        else:
            global_dict[game] = rumble

    flagmap = global_dict.get(structures.default_flag_map)
    if flagmap is None:
        flagmap = memcache.get(structures.default_flag_map)
        if flagmap is None:
            flagmapholder = structures.FlagMap.get_by_key_name(structures.default_flag_map)
            if flagmapholder is not None:
                flagmap = flagmapholder.InternalMap
                memcache.set(structures.default_flag_map, flagmap)
                global_dict[structures.default_flag_map] = flagmap
        else:
            global_dict[structures.default_flag_map] = flagmap

    flagmap = load_blob(flagmap, {})
    if not isinstance(flagmap, dict):
        flagmap = {}

    retrievetime = time.time() - parsetime - starttime

    botabots = load_blob(bota.PairingsList, [])
    if not isinstance(botabots, list):
        botabots = []
    botbbots = load_blob(botb.PairingsList, [])
    if not isinstance(botbbots, list):
        botbbots = []

    enemyScores = load_blob(rumble.ParticipantsScores, {})
    if not isinstance(enemyScores, dict):
        enemyScores = {}

    botabots = [b for b in botabots if getattr(b, 'Alive', True)]
    botbbots = [b for b in botbbots if getattr(b, 'Alive', True)]

    botbbotsDict = {b.Name: b for b in botbbots}
    commonList = []
    for ba in botabots:
        if ba.Name in botbbotsDict:
            bb = botbbotsDict[ba.Name]
            eScore = enemyScores.get(ba.Name, None)
            try:
                bb.APS = float(bb.APS)
                ba.APS = float(ba.APS)
                bb.Survival = float(bb.Survival)
                ba.Survival = float(ba.Survival)

                commonList.append(structures.ComparePair(ba, bb, eScore))
            except Exception as e:
                logging.info(str(e))

    for cp in commonList:
        package = cp.Name.split(".")[0]
        if package in flagmap:
            cp.Flag = flagmap[package]
        else:
            cp.Flag = "NONE"

    sortOrder = order.replace(" ", "_").replace("(", "").replace(")", "")
    if len(sortOrder) > 2 and sortOrder[-2] == "_":
        sortOrder = sortOrder[-1] + "_" + sortOrder[0:-2]
    out = []

    if commonList and sortOrder not in commonList[0].__dict__:
        order = "Name"
        sortOrder = "Name"

    commonList = sorted(commonList, key=attrgetter(sortOrder), reverse=reverseSort)

    sorttime = time.time() - retrievetime - parsetime - starttime
    if order == "LastUpload":
        order = "Latest Battle"

    package = bota.Name.split(".")[0]
    if package in flagmap:
        bota.Flag = flagmap[package]
    else:
        bota.Flag = "NONE"
    package = botb.Name.split(".")[0]
    if package in flagmap:
        botb.Flag = flagmap[package]
    else:
        botb.Flag = "NONE"

    gameHref = "<a href=\"Rankings?game=" + game + extraArgs + "\">" + game + "</a>"
    gameTitle = "Bot details of <b>" + botaName + " vs. " + botbName + "</b> in " + gameHref + " vs. " + str(len(commonList)) + " bots."
    out.append(structures.header(game, gameTitle, dark))

    out.append("\n<table><tr>")

    out.append("\n<th>Name</th>")
    out.append("\n<td>")
    out.append("<a href=\"BotDetails?game=" + game + "&amp;name=" + botaName.replace(" ", "%20") + extraArgs + "\">" + botaName + "</a>")
    out.append("</td><td>")
    out.append("<a href=\"BotDetails?game=" + game + "&amp;name=" + botbName.replace(" ", "%20") + extraArgs + "\">" + botbName + "</a>")

    out.append("</td><th>Diff Distribution</th></tr>")

    out.append("\n<tr><th>Flag</th>")
    out.append("\n<td>")
    out.append("<img id='flag' src=\"/flags/" + bota.Flag + ".gif\">  " + bota.Flag)
    out.append("</td><td>")
    out.append("<img id='flag' src=\"/flags/" + botb.Flag + ".gif\">  " + botb.Flag)

    out.append("</td><td rowspan=\"7\">")

    colorSurvival = numpy.array((62, 150, 81), dtype=numpy.uint32)
    colorAPS = numpy.array((204, 37, 41), dtype=numpy.uint32)
    size = 169
    a = numpy.zeros((size + 1, size + 1, 3), dtype=numpy.uint32)

    counts = numpy.zeros((size + 1, size + 1), dtype=numpy.uint32)
    for cp in commonList:
        eScore = enemyScores.get(cp.Name, None)
        if eScore:
            x = int(round(eScore.APS * 0.01 * size))
            yAPS = max(0, min(size, size - int(round((cp.A_APS - cp.B_APS + 50) * 0.01 * size))))
            a[yAPS, x, (0, 1, 2)] += colorAPS
            counts[yAPS, x] += 1

            ySurvival = [max(0, min(size, size - int(round((cp.A_Survival - cp.B_Survival + 50) * 0.01 * size))))]
            a[ySurvival, x, (0, 1, 2)] += colorSurvival
            counts[ySurvival, x] += 1
    a[counts == 0, :] = 255
    setVals = counts > 1
    for i in range(3):
        a[setVals, i] = a[setVals, i] // counts[setVals]

    midHeight = size - int(round(.5 * size))
    a[midHeight, counts[midHeight, :] == 0, :] = 127

    b_img = Image.fromarray(a.astype("uint8"), "RGB")
    c = io.BytesIO()
    b_img.save(c, format="png")
    d = c.getvalue()
    c.close()
    e = base64.b64encode(d).decode("ascii")
    out.append('<img title=\"Red = APS Diff, Green = Survival Diff" style=\"border: black 1px solid;\" alt="score distibution" src="data:image/png;base64,')
    out.append(e)
    out.append("\">")

    out.append("</td></tr>")

    APSa = 0.0
    APSb = 0.0
    Survivala = 0.0
    Survivalb = 0.0
    Winsa = 0.0
    Winsb = 0.0
    Battlesa = 0
    Battlesb = 0
    LastUploada = None
    LastUploadb = None
    for cp in commonList:
        APSa += cp.A_APS
        APSb += cp.B_APS
        Survivala += cp.A_Survival
        Survivalb += cp.B_Survival
        if cp.A_APS >= 50.0:
            Winsa += 1.0
        if cp.B_APS >= 50.0:
            Winsb += 1.0
        Battlesa += cp.A_Battles
        Battlesb += cp.B_Battles
        if LastUploada is None or cp.A_LastUpload > LastUploada:
            LastUploada = cp.A_LastUpload
        if LastUploadb is None or cp.B_LastUpload > LastUploadb:
            LastUploadb = cp.B_LastUpload

    inv_len = 1.0 / len(commonList) if commonList else 0.0
    APSa *= inv_len
    APSb *= inv_len
    Survivala *= inv_len
    Survivalb *= inv_len
    Winsa *= 100 * inv_len
    Winsb *= 100 * inv_len

    out.append("\n<tr><th>Common APS</th>")
    out.append("\n<td>" + structures.fmt(APSa) + "</td><td>" + structures.fmt(APSb) + "</td></tr>")
    out.append("\n<tr><th>Common Survival</th>")
    out.append("\n<td>" + structures.fmt(Survivala) + "</td><td>" + structures.fmt(Survivalb) + "</td>")
    out.append("</tr>")
    out.append("\n<tr><th>Common PWin</th>")
    out.append("\n<td>" + structures.fmt(Winsa) + "</td><td>" + structures.fmt(Winsb) + "</td></tr>")
    out.append("\n<tr><th>Common Battles</th>")
    out.append("\n<td>" + str(Battlesa) + "</td><td>" + str(Battlesb) + "</td></tr>")
    out.append("\n<tr><th>Common Last Upload</th>")
    out.append("\n<td>" + str(LastUploada) + "</td><td>" + str(LastUploadb) + "</td></tr>")
    out.append("\n<tr><th>Common Pairings</th>")
    out.append("\n<td colspan=\"2\" align=\"center\">" + str(len(commonList)) + "</td>")
    out.append("</tr>")

    out.append("\n</table>\n<br>\n<table>\n<tr>")

    out.append("\n<td colspan=\"3\"></td><th colspan=\"2\">" + botaName + "</th><th colspan=\"2\">" + botbName + "</th><td colspan=\"3\">")
    out.append("</td></tr><tr class=\"dim\">")

    headings = [
        "  ",
        "Flag",
        "Name",
        "APS (A)",
        "Survival (A)",
        "APS (B)",
        "Survival (B)",
        "Diff APS",
        "Diff Survival",
        "Opponent APS"
    ]
    for heading in headings:
        headinglink = heading
        sortedBy = (order == heading)
        if sortedBy and reverseSort:
            heading = "-" + heading
            headinglink = heading
        elif not sortedBy:
            headinglink = "-" + headinglink

        orderHref = "<a href=\"BotCompare?game=" + game + "&amp;bota=" + botaName.replace(" ", "%20") + "&amp;botb=" + botbName.replace(" ", "%20") + "&amp;order=" + headinglink.replace(" ", "%20") + extraArgs + "\">" + heading + "</a>"
        if sortedBy:
            out.append("\n<th class=\"sortedby\">" + orderHref + "</th>")
        else:
            out.append("\n<th>" + orderHref + "</th>")

    out.append("\n</tr>")
    rank = 1
    highlightKey = [False, False, False, True, True, True, True, True, True, True]
    mins = [0, 0, 0, 40, 40, 40, 40, -0.1, -5, 40]
    maxs = [0, 0, 0, 60, 60, 60, 60, 0.1, 5, 60]
    for cp in commonList:
        if rank > lim:
            break

        botName = cp.Name
        botNameHref = "<a href=\"BotDetails?game=" + game + "&amp;name=" + botName.replace(" ", "%20") + extraArgs + "\">" + botName + "</a>"
        flagtag = "<img id='flag' src=\"/flags/" + cp.Flag + ".gif\">"
        cells = [
            str(rank),
            flagtag,
            botNameHref,
            cp.A_APS,
            cp.A_Survival,
            cp.B_APS,
            cp.B_Survival,
            cp.Diff_APS,
            cp.Diff_Survival,
            cp.Opponent_APS,
        ]

        out.append("\n<tr>")

        for i, cell in enumerate(cells):
            if highlightKey[i]:
                if cell < mins[i]:
                    out.append("\n<td class=\"red\">" + structures.fmt(cell) + "</td>")
                elif cell > maxs[i]:
                    out.append("\n<td class=\"green\">" + structures.fmt(cell) + "</td>")
                else:
                    out.append("\n<td>" + structures.fmt(cell) + "</td>")
            else:
                out.append("\n<td>" + structures.fmt(cell) + "</td>")
        out.append("\n</tr>")

        rank += 1

    out.append("</table>")
    htmltime = time.time() - sorttime - retrievetime - parsetime - starttime
    elapsed = time.time() - starttime
    if timing:
        out.append("<br>\n Page served in " + str(int(round(elapsed * 1000))) + "ms. Bot cached: " + str(cached))
        out.append("\n<br> parsing: " + str(int(round(parsetime * 1000))))
        out.append("\n<br> retrieve: " + str(int(round(retrievetime * 1000))))
        out.append("\n<br> sort: " + str(int(round(sorttime * 1000))))
        out.append("\n<br> html generation: " + str(int(round(htmltime * 1000))))
    out.append("</body></html>")

    return "".join(out)
