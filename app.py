# app code
# will run the Agritrial dashboard as a local website

from flask import Flask, render_template
from chart import generate_chart

app = Flask(__name__)

@app.route("/")
def dashboard():
    # will generate a fresh chart every time the page loads
    generate_chart()
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)