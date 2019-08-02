import json
import automate
import boto3
import dateutil.parser
import pytz
from webexteamssdk import WebexTeamsAPI
from meraki.meraki_client import MerakiClient


def add_or_update_webhook(cfg, api, client, path):
    ret = ""
    if path == "update":
        webhooks = api.webhooks.list()
        if webhooks:
            for wh in webhooks:
                if wh.name == cfg["teams_bot"]["app_name"]:
                    api.webhooks.update(webhookId=wh.id, name=cfg["teams_bot"]["app_name"], targetUrl=cfg["teams_bot"]["app_url"])
                    print("Webhook Updated")
                    ret += "Webex Teams Webhook Updated -- " + cfg["teams_bot"]["app_url"] + "<br>"
        else:
            api.webhooks.create(name=cfg["teams_bot"]["app_name"], targetUrl=cfg["teams_bot"]["app_url"], resource="messages", event="created")
            print("Webhook Created")
            ret += "Webex Teams Webhook Created -- " + cfg["teams_bot"]["app_url"] + "<br>"

        networks = client.networks.get_organization_networks({"organization_id": cfg["deploy"]["orgid"]})
        for network in networks:
            webhooks = client.http_servers.get_network_http_servers(network["id"])
            if webhooks:
                for webhook in webhooks:
                    if webhook["name"] == cfg["teams_bot"]["app_name"]:
                        client.http_servers.update_network_http_server({"network_id": network["id"], "id": webhook["id"], "update_network_http_server": {"name": cfg["teams_bot"]["app_name"], "url": cfg["teams_bot"]["app_url"]}})
                        ret += "Meraki Webhook Updated -- " + network["name"] + "<br>"
            else:
                client.http_servers.create_network_http_server({"network_id": network["id"], "create_network_http_server": {"name": cfg["teams_bot"]["app_name"], "url": cfg["teams_bot"]["app_url"]}})
                ret += "Meraki Webhook Created -- " + network["name"] + "<br>"

        return "Service OK<br>" + ret
    else:
        return "Service OK -- Use <a href='/update'>/update</a> or <a href='?update'>?update</a> to update Webex Teams and Meraki Webhooks"


def process_meraki_webhook(event, cfg, api, client):
    print("process_meraki_webhook -", event)
    # The Meraki Webhooks will be parsed and sent to a desginated Webex Teams Room
    # The roomId for this room is stored in a file in Amazon S3, so we need to get
    # that file and look up the roomId
    s3 = boto3.resource('s3', aws_access_key_id=cfg["amazon"]["aws_access_key_id"], aws_secret_access_key=cfg["amazon"]["aws_secret_access_key"])
    response = s3.Object(cfg["amazon"]["s3_bucket"], 'alert_roomid.cfg').get()
    rid = response['Body'].read().decode("utf-8")

    # Parse event data
    tz = pytz.timezone('America/Los_Angeles')
    utc_dt = dateutil.parser.parse(event['occurredAt'])
    dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(tz)
    strdt = dt.strftime("%I:%M %p %Z on %B %d")
    print(dt, strdt)
    alert = event['alertType']
    data = event['alertData']
    name = data['name'] if 'name' in data else ''
    network_link = event['networkUrl']
    device = event['deviceName'] if 'deviceName' in event else ''
    network = event['networkName'].replace('@', '') if 'networkName' in event else ''
    if network:
        network_link = event['networkUrl']
    if device:
        device_link = event['deviceUrl']

    ul_list = ["Internet 1", "Internet 2"]
    if alert.lower() == "uplink status changed":
        ulnum = int(data['uplink']) if 'uplink' in data else 99
        cellnum = int(data['isCellular']) if 'isCellular' in data else 99
        if ulnum <= len(ul_list):
            ul = ul_list[ulnum]
        else:
            if cellnum != 99:
                ul = "Cellular"
            else:
                ul = "unknown Uplink (" + str(data) + ")"
        message = "There has been 1 failover event detected:<br><br>At " + strdt + ", the security appliance in the " + f'_[{network}]({network_link})_' + " network switched to using " + ul + " as its uplink."
        data = ""
    else:
        message = f'**{alert}**'

        if name:
            message += f' - _{name}_'
        message += f': [{network}]({network_link})'
        if device:
            message += f' - _[{device}]({device_link})_'

    print("process_meraki_webhook -", rid, data, message)
    # Add more alert information and format JSON
    if data:
        message += f'  \n```{json.dumps(data, indent=2, sort_keys=True)}'[:-1]  # screwy Webex Teams formatting
        api.messages.create(roomId=rid, markdown=message)

    # Send the webhook without alert data
    elif message != '':
        api.messages.create(roomId=rid, markdown=message)


# Get user's name
def get_name(data):
    if data['displayName']:
        return data['displayName']
    else:
        return f'{data["firstName"]} {data["lastName"]}'


# Function to check whether message contains one of multiple possible options
def message_contains(text, options):
    message = text.strip().lower()
    for option in options:
        if option in message:
            return True
    return False


# Clear your screen and display Miles!
def clear_screen():
    return '''```
                                   ./(((((((((((((((((/.
                             *(((((((((((((((((((((((((((((
                         .(((((((((((((((((((((((((((((((((((/
                       ((((((((((((((((((((((((((((((((((((((((/
                    ,((((((((((((((((((((((((((((((((((((((((((((
                  .((((((((((((((((((((     ((((((/     ((((((((((,
                 ((((((((((((((((((((((     ((((((/     (((((((((((
               /((((((((((((((((((((((((((((((((((((((((((((((((((((
              ((((((((((((((((((((((((((((((((((((((((((((((((((((((*
             ((((((((((((((((((((((((((((((((((((((((((((((((((((((((
            (((((((((((((((((((((((((((((((((((((((((((((((((((((((((
           ((((((((((((((((((((((((     ((((((((((((((/     (((((((((
          ,((((((((((((((((((((((((     ((((((((((((((/     ((((((((/
          (((((((((((((((((((((((((    .//////////////*    .((((((((
         ,(((((((((((((((((((((((((((((/              ((((((((((((.
         ((((((((((((((((((((((((((((((/              (((((((((((
         (((((((((((((((((((((((((((((((((((((((((((((((((((((((*
        .(((((((((((((((((((((((((((((((((((((((((((((((((((((*
        /((((((((((((((((((((((((((((((((((((((((((((((((((*
        (((((((((((((((((((((((((((((((((((((((((((((((*
        (((((((((((/.                     ....
        (((((((/
        (((((
        (((
        /.
    '''


def process_teams_webhook(event, cfg, api, client):
    print("process_teams_webhook -", event)
    # Continue to process message
    m_data = api.messages.get(event["data"]["id"])
    message = m_data.text
    files = m_data.files

    # Stop if last message was bot's own, or else loop to infinite & beyond!
    if event["data"]["personEmail"] == cfg["teams_bot"]["app_email"]:
        return {'statusCode: 204'}

    # Prevent other users from using personal bot
    sender_emails = event["data"]["personEmail"]
    allow_interaction = 0
    allow_email_list = cfg["teams_bot"]["opt_user_restriction"].split(",")
    for em in allow_email_list:
        if em.strip() in sender_emails:
            allow_interaction = 1

    if allow_interaction == 0:
        p = api.people.get(personId=event["data"]["personId"])
        api.messages.create(roomId=event["data"]["roomId"], html=f'Hi **{get_name(p)}**, I\'m not allowed to chat with you! ⛔️')
        return {'statusCode': 200}
    else:
        print(f'Message received: {message}')

        # Create & send response depending on input message
        if message_contains(message, ['help']):
            msg = "Here are the commands you can use:<br><br>"
            msg += "automate deploy [network-name]<br>"
            msg += "automate rename [old-network-name] [new-network-name]<br>"
            msg += "automate delete [network-name]<br>"
            msg += "automate bulk deploy [attach csv file]<br>"
            msg += "automate bulk delete [attach csv file]<br>"
            api.messages.create(roomId=event["data"]["roomId"], html=msg)

        # Get org-wide device statuses
        elif message_contains(message, ['automate']):
            automate.process_automate(files, message, event, cfg, api, client)

        # Clear screen to reset demos
        elif message_contains(message, ['clear']):
            api.messages.create(roomId=event["data"]["roomId"], html=clear_screen())

        # Catch-all if bot doesn't understand the query!
        else:
            api.messages.create(roomId=event["data"]["roomId"], html='Make a wish! 🤪')

        # Let chat app know success
        return {
            'statusCode': 200,
            'body': json.dumps('message received')
        }


def run(cfg, event, path):
    api = WebexTeamsAPI(access_token=cfg["teams_bot"]["token"])
    client = MerakiClient(cfg["meraki"]["token"])

    if "organizationId" in event:
        return process_meraki_webhook(event, cfg, api, client)
    elif event:
        return process_teams_webhook(event, cfg, api, client)
    else:
        ret = add_or_update_webhook(cfg, api, client, path)
        return {
            'statusCode': 200,
            'body': "success -- " + str(ret)
        }
