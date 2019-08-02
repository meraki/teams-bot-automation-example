import bot
import csv
import time
import requests
from io import BytesIO
import boto3


def delete_network_by_name(netname, event, cfg, client):
    print("delete_network_by_name --", netname)
    response = client.networks.get_organization_networks({"organization_id": cfg["deploy"]["orgid"]})

    foundnet = 0
    if True:
        for n in response:
            for nn in netname:
                if n["name"].lower() == nn.lower():
                    net_id = n["id"]
                    response = client.networks.delete_network(net_id)
                    print("delete_network_by_name --", n)
                    foundnet += 1
                    if foundnet == len(netname):
                        break

        if foundnet == len(netname):
            return True
            
        return False


def update_network_by_name(oldname, newname, event, cfg, client):
    print("update_network_by_name --", oldname)
    response = client.networks.get_organization_networks({"organization_id": cfg["deploy"]["orgid"]})

    foundnet = 0
    print("update_network_by_name --")
    if True:
        for n in response:
            print("update_network_by_name --", n)
            if n["name"].lower() == oldname.lower():
                net_id = n["id"]
                response = client.networks.update_network({"network_id": net_id, "update_network": {"name": newname}})
                print("update_network_by_name --")
                foundnet = 1

        if foundnet == 1:
            return True
            
        return False


def hold_for_ab_completion(response, client, cfg, delay):
    abid = response["id"]
    while response["status"]["completed"] is False and response["status"]["failed"] is False:
        print("hold_for_ab_completion -- pausing to allow action batch to complete... ab id=", abid)
        response = client.action_batches.get_organization_action_batch({"organization_id": cfg["deploy"]["orgid"], "id": abid})
        time.sleep(delay)
    if response["status"]["failed"] is True:
        print("hold_for_ab_completion -- action batch failed.", response)
        return False

    return True


def deploy_network(netname, thems, themr, themx, ms_access, ms_vvlan, event, cfg, client):
    # although dashboard lets you have duplicate network names, we are going to
    # prevent that here. check current network names to ensure this one does
    # not already exist

    print("deploy_network --", netname)
    response = client.networks.get_organization_networks({"organization_id": cfg["deploy"]["orgid"]})
    
    foundnet = 0
    netids = {}
    # print(netname, thems, themr, themx)
    for n in range(0, len(netname)):
        print(n, netname[n], thems[n], themr[n], themx[n])
        netids[netname[n]] = {"ms": thems[n], "mr": themr[n], "mx": themx[n]}

    if True:
        for n in response:
            for nn in netname:
                if n["name"].lower() == nn.lower():
                    print("deploy_network --", n)
                    foundnet = 1
                    break

    if foundnet == 1:
        print("deploy_network -- error; found duplicate network name")
        return False
    else:
        print("deploy_network -- creating new network(s) from template")
        # If there is just one network, use a regular creation; otherwise, use an action batch
        if len(netname) == 1:
            response = client.networks.create_organization_network({"organization_id": cfg["deploy"]["orgid"], "create_organization_network": {"name": netname[0], "type": "switch wireless appliance", "copyFromNetworkId": cfg["deploy"]["templatenetwork"]}})
            # print(netids, netids[netname[0]], response)
            netids[netname[0]]["id"] = response["id"]
        else:
            action_list = []
            for p in netname:
                action_list.append({"resource": "/organizations/" + cfg["deploy"]["orgid"] + "/networks", "operation": "create", "body": {"name": p, "type": "switch wireless appliance", "copyFromNetworkId": cfg["deploy"]["templatenetwork"]}})

            response = client.action_batches.create_organization_action_batch({"organization_id": cfg["deploy"]["orgid"], "create_organization_action_batch": {"confirmed": True, "synchronous": True, "actions": action_list}})
            if not hold_for_ab_completion(response, client, cfg, 3):
                return False

            response = client.networks.get_organization_networks({"organization_id": cfg["deploy"]["orgid"]})

            foundnet = 0
            if True:
                for n in response:
                    for nn in netname:
                        if n["name"].lower() == nn.lower():
                            print("deploy_network --", n)
                            netids[nn]["id"] = n["id"]

        if True:
            action_list = []
            for netid in netids:
                print("deploy_network -- network created. adding devices to net ", netids[netid])

                devs = [netids[netid]["ms"], netids[netid]["mr"], netids[netid]["mx"]]
                for p in devs:
                    action_list.append({"resource": "/networks/" + netids[netid]["id"] + "/devices", "operation": "claim", "body": {"serial": p}})

            print(action_list)
            response = client.action_batches.create_organization_action_batch({"organization_id": cfg["deploy"]["orgid"], "create_organization_action_batch": {"confirmed": True, "synchronous": False, "actions": action_list}})
            if not hold_for_ab_completion(response, client, cfg, 5):
                return False
            # r1 = client.devices.claim_network_devices({"network_id": netid, "claim_network_devices": {"serial": thems}})
            # r2 = client.devices.claim_network_devices({"network_id": netid, "claim_network_devices": {"serial": themr}})
            # r3 = client.devices.claim_network_devices({"network_id": netid, "claim_network_devices": {"serial": themx}})

            if True:
                push_port_config(action_list, thems, ms_access, ms_vvlan, event, cfg, client)
                return True


def push_port_config(dev_action_list, thems, ms_access, ms_vvlan, event, cfg, client):
    print("push_port_config -- entry")

    action_list = []
    for ms in range(0, len(thems)):
        if ms_access[ms].find("-") > 0:
            arr_acc = ms_access[ms].split("-")
            print("push_port_config -- ", arr_acc)
            list_access = [i for i in range(int(arr_acc[0]), int(arr_acc[1])+1)]
            print("push_port_config -- ", list_access)
        else:
            list_access = ms_access[ms].split(",")

        for p in list_access:
            action_list.append({"resource": "/devices/" + thems[ms] + "/switchPorts/" + str(p).strip(),"operation": "update","body": {"type": "access", "voiceVlan": ms_vvlan[ms]}})

    print(action_list)
    response = client.action_batches.create_organization_action_batch({"organization_id": cfg["deploy"]["orgid"], "create_organization_action_batch": {"confirmed": True, "synchronous": False, "actions": action_list}})
    rjson = response
    print("push_port_config --", str(rjson["id"]))

    return True


def remove_unavailable(dev_list, org_devs):
    new_list = [x.strip() for x in dev_list]
    
    for o in org_devs:
        dsn = o["serial"]
        print(dsn, new_list)
        if dsn in new_list:
            new_list.remove(dsn)

    return new_list


def process_automate(files, message, event, cfg, api, client):
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {cfg["teams_bot"]["token"]}'
    }

    org_devs = client.organizations.get_organization_device_statuses(id=cfg["deploy"]["orgid"])

    ms_list = cfg["deploy"]["ms_list"]
    mr_list = cfg["deploy"]["mr_list"]
    mx_list = cfg["deploy"]["mx_list"]
    ms_list = remove_unavailable(ms_list, org_devs)
    mr_list = remove_unavailable(mr_list, org_devs)
    mx_list = remove_unavailable(mx_list, org_devs)
    parmlist = message.strip().split(" ")
    netname = parmlist[len(parmlist) - 1]
    
    if bot.message_contains(message, ['bulk deploy']):
        if len(files) > 0:
            f = files[0]
            # Not sure if there is an API friendly way to do this...
            r = requests.get(f, allow_redirects=True, headers=headers)
            c = r.content.decode("UTF-8")
            creader = csv.reader(c.splitlines(), delimiter=',', quotechar='"')
            next(creader)
            netname = []
            thems = []
            themr = []
            themx = []
            ms_access = []
            ms_vvlan = []
            msg = ""
            for row in creader:
                netname.append(row[0])
                thems.append(row[1])
                themr.append(row[2])
                themx.append(row[3])
                ms_access.append(row[4])
                ms_vvlan.append(row[5])
                msg += 'Will deploy "' + row[1] + '", "' + row[2] + '", and "' + row[3] + '" to new network "' + row[0] + '"\n'
            msg += "Bulk deploy action batch submitted!\n"
            api.messages.create(roomId=event["data"]["roomId"], html=msg)
            ret = deploy_network(netname, thems, themr, themx, ms_access, ms_vvlan, event, cfg, client)
            api.messages.create(roomId=event["data"]["roomId"], html="Bulk deploy completed!")
        else:
            print("No files found.")
            api.messages.create(roomId=event["data"]["roomId"], html='Make sure you attach the .csv file to import.')

    elif bot.message_contains(message, ['bulk delete']):
        if len(files) > 0:
            f = files[0]
            r = requests.get(f, allow_redirects=True, headers=headers)
            c = r.content.decode("UTF-8")
            creader = csv.reader(c.splitlines(), delimiter=',', quotechar='"')
            next(creader)
            netname = []
            msg = ""
            for row in creader:
                netname.append(row[0])
                msg += 'Will delete network "' + row[0] + '"\n'
            msg += "Bulk delete action batch submitted!\n"
            api.messages.create(roomId=event["data"]["roomId"], html=msg)
            ret = delete_network_by_name(netname, event, cfg, client)
            api.messages.create(roomId=event["data"]["roomId"], html="Bulk delete completed!")
        else:
            print("No files found.")
            api.messages.create(roomId=event["data"]["roomId"], html='Make sure you attach the .csv file to delete.')

    elif bot.message_contains(message, ['deploy']):
        if len(ms_list) > 0 and len(mr_list) > 0 and len(mx_list) > 0:
            thems = ms_list[0]
            themr = mr_list[0]
            themx = mx_list[0]
            api.messages.create(roomId=event["data"]["roomId"], html='Deploying "' + thems + '", "' + themr + '", and "' + themx + '" to new network "' + netname + '"...')
            ret = deploy_network([netname], [thems], [themr], [themx], [cfg["deploy"]["msaccess"]], [cfg["deploy"]["msvvlan"]], event, cfg, client)
            if ret:
                api.messages.create(roomId=event["data"]["roomId"], html='Devices deployed successfully!')
            else:
                api.messages.create(roomId=event["data"]["roomId"], html='Unable to deploy devices to network. 😫')
        else:
            api.messages.create(roomId=event["data"]["roomId"], html='All devices have already been deployed!')

    elif bot.message_contains(message, ['delete']):
        api.messages.create(roomId=event["data"]["roomId"], html='Deleting network "' + netname + '"...')
        print("process_automate -- preparing to delete", netname)
        ret = delete_network_by_name([netname], event, cfg, client)
        print("process_automate -- delete attempted", ret)

        if ret:
            api.messages.create(roomId=event["data"]["roomId"], html='Network deleted successfully!')
        else:
            api.messages.create(roomId=event["data"]["roomId"], html='Unable to delete network. 😫')

    elif bot.message_contains(message, ['rename']):
        # netnames = netname.split(" ")
        # oldname = netnames[len(netnames)-2]
        # newname = netnames[len(netnames)-1]
        oldname = parmlist[len(parmlist) - 2]
        newname = parmlist[len(parmlist) - 1]
        api.messages.create(roomId=event["data"]["roomId"], html='Renaming network "' + oldname + '" to "' + newname + '"...')
        ret = update_network_by_name(oldname, newname, event, cfg, client)

        if ret:
            api.messages.create(roomId=event["data"]["roomId"], html='Network renamed successfully!')
        else:
            api.messages.create(roomId=event["data"]["roomId"], html='Unable to rename network. 😫')

    elif bot.message_contains(message, ['monitor']):
        rid = event["data"]["roomId"]
        s3 = boto3.client('s3', aws_access_key_id=cfg["amazon"]["aws_access_key_id"], aws_secret_access_key=cfg["amazon"]["aws_secret_access_key"])
        fileobj = BytesIO(rid.encode("utf-8"))
        print("updating file for rid", rid)
        s3.upload_fileobj(fileobj, cfg["amazon"]["s3_bucket"], 'alert_roomid.cfg')
        api.messages.create(roomId=event["data"]["roomId"], html='Meraki Alert Webhooks will be delivered to this Room.')

    else:
        msg = 'Did not recognize the specified automation request... 😫<br>'
        api.messages.create(roomId=event["data"]["roomId"], html=msg)
