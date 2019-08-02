import json
import bot


# https://stackoverflow.com/questions/434641/how-do-i-set-permissions-attributes-on-a-file-in-a-zip-file-using-pythons-zip/434689#434689
# Main Lambda function
def lambda_handler(event, context):
    # Load configuration variables
    f = open("config.json", "r")
    c = json.loads(f.read())

    path = ""
    jdata = {}
    if event:
        if "queryStringParameters" in event and event["queryStringParameters"] is not None:
            if "update" in event["queryStringParameters"]:
                path = "update"

        if event["body"] and event["body"] != "":
            jdata = json.loads(event["body"])

    # Need to find path for webhook updates. Either /update or ?update.
    print(event, context)
    r = bot.run(c, jdata, path)

    if r:
        if "body" in r:
            if "statusCode" in r:
                return {
                    'statusCode': r["statusCode"],
                    'body': r["body"]
                }
            else:
                return {
                    'statusCode': 200,
                    'body': r["body"]
                }
        else:
            if "statusCode" in r:
                return {
                    'statusCode': r["statusCode"],
                    'body': ""
                }

    return {
        'statusCode': 200,
        'body': "success"
    }
