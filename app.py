from flask import Flask, request, jsonify, render_template
import pulp
import itertools

import numpy as np
import os
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Set up logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.form
        file = request.files['etc_file']

        year = data['year']
        S = int(data['days'])
        ADP = float(data['dew_point'])
        Actual = float(data['yield'])
        WC0 = float(data['water_content'])

        # Constants
        FC = 59
        PAW = 55.5
        RAW = 22.2
        theta = 34.4
        MAD = 24.6

        # Save the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # The decision variable
        x = pulp.LpVariable.dicts("x", range(1, S + 1), lowBound=0, cat='Continuous')

        # Percentages
        x_i = [round(0.2 * RAW), round(0.22 * RAW)]

        # Variables to store optimal solution details
        optimal_total_water = MAD * S * 10

        # Set lower and upper bounds
        for p in range(len(x_i)):
            for i in range(1, S + 1):
                x[i].lowBound = 0
                x[i].upBound = MAD

        # Read the Etc values
        def read_etc_values(file_path):
            with open(file_path, 'r') as file:
                etc_values = [float(line.strip()) for line in file]
            return etc_values

        Etc = read_etc_values(file_path)

        arr_days = [x_i for _ in range(S)]
        combinations = itertools.product(*arr_days)
        chunk = []
        summation = []
        for combo in combinations:
            chunk.append(combo)
            summation.append(sum(combo))

        total_wc = []
        days_index = []
        days_irrigated = []
        for i in range(len(chunk)):
            water_content = np.zeros(S)
            water_content[0] = WC0
            total_wc.append(water_content)

        new_summation = []
        num_of_irri_days = 0
        for j in range(len(chunk)):
            i = 0
            iterator = 0
            for day in range(1, S):
                if total_wc[j][day - 1] <= theta:
                    total_wc[j][day] = total_wc[j][day - 1] - Etc[day] + chunk[j][i]
                    days_index.append(day + 1)
                    num_of_irri_days += 1
                    i += 1
                    iterator += chunk[j][i]

                if total_wc[j][day-1] > theta:
                    total_wc[j][day] = total_wc[j][day - 1] - Etc[day]
            days_irrigated.append(days_index)
            new_summation.append(iterator)

        optimum_Z = []
        optimum_y = []
        for f in range(len(chunk)):
            Z = new_summation[f] * 10
            y = (-1.3 + (0.2 * ADP) + (0.003 * Z))
            if Z < optimal_total_water and y >= Actual:
                optimum_Z.append(Z)
                optimum_y.append(y)

        optimal_Z = 0
        optimal_y = 0
        for i in range(1, len(optimum_Z)):
            if optimum_Z[i] < optimum_Z[i-1] and optimum_y[i] > optimum_y[i-1]:
                optimal_Z = optimum_Z[i]
                optimal_y = optimum_y[i]

        return jsonify(optimal_Z=optimal_Z, optimal_y=optimal_y)
    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True)
