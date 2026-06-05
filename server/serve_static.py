from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import os

# Flask will serve this app.js from a dedicated static directory
app = None  # Will be set by backend_api

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
