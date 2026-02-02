from flask import Flask, render_template
from Karaoke.Karaoke import karaoke
from Scorekeeper.scoring import scoring
app = Flask(__name__)
app.register_blueprint(karaoke, url_prefix="/karaoke")
app.register_blueprint(scoring, url_prefix="/scoring")

# Route 3: Main to redirect to others
@app.route('/', methods=['GET'])
def show_redirects():
    return render_template("index.html")


if __name__ == '__main__':
    app.run(debug=True)
