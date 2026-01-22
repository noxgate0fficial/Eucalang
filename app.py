from flask import Flask, request, jsonify, render_template
from interpreter import Interpreter
import io, sys

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_code():
    code = request.json.get("code", "")
    inputs = request.json.get("inputs", {})

    try:
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()

        Interpreter(code, inputs=inputs).run()

        sys.stdout = old_stdout
        output = mystdout.getvalue()
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"output": str(e)})

if __name__ == "__main__":
    app.run(debug=True)
