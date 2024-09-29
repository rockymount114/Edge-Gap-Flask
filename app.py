from flask import Flask, render_template, request, send_file, session, flash, redirect, url_for
import os
import pandas as pd
import re
from werkzeug.utils import secure_filename
from config import columns, widths

app = Flask(__name__)
app.secret_key = '1030d253-f896-45a8-aed9-dae5cd9d4834'  # Make sure to use a strong, random secret key in production

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

def convert_to_csv(folder_path, widths, columns):
    all_dataframes = []
    column_widths = widths
    column_headers = columns

    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            file_path = os.path.join(folder_path, filename)
            df = pd.read_fwf(file_path, widths=column_widths, dtype=object)
            df.columns = column_headers
            
            c02 = df['PERC6'] == 'C02' #filter out C02 district for the City of Rocky Mount
            df = df[c02]
            #### if you want double check file, turn this line on
            # df['NOTES'] = os.path.splitext(filename)[0] 
            
            all_dataframes.append(df)

    if not all_dataframes:
        raise ValueError("No DataFrames to concatenate. Please check the data source.")

    final_dataframe = pd.concat(all_dataframes, ignore_index=True)
    final_dataframe = final_dataframe.fillna('')
    final_dataframe.columns = column_headers
    return final_dataframe

def export_to_fixed_width(df, min_year, max_year, widths):
    # Define the output file path
    output_file = f"download/{min_year}-{max_year} Edge Gap Billing_{len(df)}.txt"
    
    with open(output_file, 'w') as f:
        for index, row in df.iterrows():
            line = ""
            for i, width in enumerate(widths):
                # Create fixed-width string for each column
                cell_value = str(row[i])[:width]  # Truncate to width
                line += cell_value.ljust(width)  # Pad with spaces
            f.write(line.rstrip() + '\n')  # Write the line to the file, removing trailing spaces


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'folder' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        files = request.files.getlist('folder')
        if not files or files[0].filename == '':
            flash('No selected files', 'error')
            return redirect(request.url)
        
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_folder')
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        years = []
        file_names = []
        for file in files:
            if file and file.filename.endswith('.txt'):
                filename = secure_filename(file.filename)
                file.save(os.path.join(folder_path, filename))
                file_names.append(filename)
                match = re.search(r'(\d{4})', filename)
                if match:
                    year = int(match.group(1))
                    years.append(year)
        
        try:
            df = convert_to_csv(folder_path, widths=widths, columns=columns)
            
            min_year = min(years) if years else 0
            max_year = max(years) if years else 0
            output_filename = f"{min_year}-{max_year} Edge Gap Billing_{len(df)}.csv"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            df.to_csv(output_path, index=False, header=False)  ### set False if don't need file header
            
            export_to_fixed_width(df, min_year, max_year, widths)
            
            # Clean up temporary folder
            for file in os.listdir(folder_path):
                os.remove(os.path.join(folder_path, file))
            os.rmdir(folder_path)
            
            session['file_names'] = file_names
            session['output_filename'] = output_filename
            
            flash('Conversion successful!', 'success')
            
            
            
            return redirect(url_for('upload_file'))
        
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('upload_file'))
    
    return render_template('upload.html', 
                           file_names=session.get('file_names'), 
                           output_filename=session.get('output_filename'))  

@app.route('/download')
def download_file():
    output_filename = session.get('output_filename')
    if output_filename:
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        return send_file(output_path, as_attachment=True)
    else:
        flash('No file to download', 'error')
        return redirect(url_for('upload_file'))

if __name__ == '__main__':
    app.run()