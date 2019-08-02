from flask import Flask, request, Response
import json
import os
import bot

# ========================================================
# Load required parameters from environment variables
# ========================================================

# If there is a PORT environment variable, use that to map the Flask port. Used for Heroku.
# If no port set, use default of 5000.
app_port = os.getenv("PORT")
app_ssl = os.getenv("USESSL")
if not app_port:
    app_port = 5000
else:
    app_port = int(app_port)

if app_ssl:
    app_ssl = True


def load_config():
    out_config = {}

    f = open("config.json", "r")
    jf = json.loads(f.read())
    for p_category in jf:
        if p_category not in out_config:
            out_config[p_category] = {}

        for p_variable in jf[p_category]:
            lp = os.getenv(p_category.upper() + "_" + p_variable.upper())
            if lp:
                out_config[p_category][p_variable] = lp
            else:
                out_config[p_category][p_variable] = jf[p_category][p_variable]

    return out_config


# -- Application Setup
cfg = load_config()
app = Flask(__name__)


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    get_update = request.args.get('update')
    if get_update is not None:
        if not path:
            path = "update"

    try:
        jdata = request.get_json(force=True)
    except:
        jdata = {}

    r = bot.run(cfg, jdata, path)

    if r:
        if "body" in r:
            if "statusCode" in r:
                return r["body"], r["statusCode"]
            else:
                return r["body"]
        else:
            if "statusCode" in r:
                return "", r["statusCode"]

    return ""


# -- Main function
if __name__ == '__main__':
    # Run Flask
    if app_ssl:
        app.run(debug=True, host='0.0.0.0', port=app_port, ssl_context='adhoc')
    else:
        app.run(debug=True, host='0.0.0.0', port=app_port)
