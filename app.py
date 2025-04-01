from flask import Flask, request, render_template, redirect, url_for, flash, session
import os
from dotenv import load_dotenv
import psycopg2
from urllib.parse import urlparse
import re  

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Configuración de la DB (usando DB_URL de Render)
db_url = urlparse(os.getenv('DB_URL'))
DB_CONFIG = {
    'dbname': db_url.path[1:],
    'user': db_url.username,
    'password': db_url.password,
    'host': db_url.hostname,
    'port': db_url.port,
    'sslmode': 'require'
}

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL,
            apellido_paterno VARCHAR(50) NOT NULL,
            apellido_materno VARCHAR(50),
            fecha_nacimiento DATE NOT NULL,
            curp VARCHAR(18) UNIQUE,
            celular VARCHAR(10),
            email VARCHAR(100) UNIQUE,
            estudios VARCHAR(20)
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        # 1. Recoger datos del formulario
        datos = {
            'nombre': request.form.get('nombre', '').strip(),
            'apellido_paterno': request.form.get('apellido_paterno', '').strip(),
            'apellido_materno': request.form.get('apellido_materno', '').strip(),
            'fecha_nacimiento': request.form.get('fecha_nacimiento'),
            'curp': request.form.get('curp', '').upper().strip(),
            'celular': request.form.get('celular', '').strip(),
            'email': request.form.get('email', '').lower().strip(),
            'estudios': request.form.get('estudios')
        }

        # 2. Validaciones básicas
        errores = {}
        
        # Validaciones de nombre
        if not datos['nombre']:
            errores['nombre'] = 'El nombre es obligatorio'
        elif not re.match(r'^[A-Za-zÁ-Úá-úñÑüÜ\s]+$', datos['nombre']):
            errores['nombre'] = 'Solo letras y espacios (sin números o símbolos)'

        # Validaciones de apellido paterno
        if not datos['apellido_paterno']:
            errores['apellido_paterno'] = 'El apellido paterno es obligatorio'
        elif not re.match(r'^[A-Za-zÁ-Úá-úñÑüÜ]+$', datos['apellido_paterno']):
            errores['apellido_paterno'] = 'Solo letras (sin espacios, números o símbolos)'

        # Validaciones de apellido materno
        if not datos['apellido_materno']:
            errores['apellido_materno'] = 'El apellido materno es obligatorio'       
        elif not re.match(r'^[A-Za-zÁ-Úá-ú]+$', datos['apellido_materno']):
            errores['apellido_materno'] = 'Solo letras (sin espacios, números o símbolos)'

        # Validacion de fecha de nacimiento
        if not datos['fecha_nacimiento']:
            errores['fecha_nacimiento'] = 'La fecha de nacimiento es obligatoria'
            
        # Validación de CURP (expresión regular)
        if not re.match(r'^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z]{2}$', datos['curp']):
            errores['curp'] = 'El CURP no tiene un formato válido'
            
        # Validación de celular (10 dígitos)
        if not datos['celular'].isdigit() or len(datos['celular']) != 10:
            errores['celular'] = 'El celular debe tener 10 dígitos numéricos'
            
        # Validación de email
        if '@' not in datos['email'] or '.' not in datos['email'].split('@')[1]:
            errores['email'] = 'Ingrese un email válido'

        # 3. Manejo de errores
        if errores:
            return render_template('registro.html', 
                                datos=datos, 
                                errores=errores)

        # 4. Si no hay errores, proceder
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Verificar duplicados
            cursor.execute("SELECT 1 FROM usuarios WHERE curp = %s OR email = %s", 
                         (datos['curp'], datos['email']))
            if cursor.fetchone():
                flash('Error: El CURP o email ya están registrados', 'danger')
                return render_template('registro.html', datos=datos)
            
            # Guardar en sesión para confirmación
            session['datos_registro'] = datos
            return redirect(url_for('confirmacion'))
            
        except psycopg2.Error as e:
            flash(f'Error de base de datos: {str(e)}', 'danger')
            return render_template('registro.html', datos=datos)
        finally:
            if 'conn' in locals() and conn:
                conn.close()
    
    # GET request
    return render_template('registro.html')

@app.route('/confirmacion', methods=['GET', 'POST'])
def confirmacion():
    if 'datos_registro' not in session:
        return redirect(url_for('registro'))
    
    datos = session['datos_registro']
    
    if request.method == 'POST':
        if 'confirmar' in request.form:
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO usuarios 
                    (nombre, apellido_paterno, apellido_materno, fecha_nacimiento, curp, celular, email, estudios)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    datos['nombre'],
                    datos['apellido_paterno'],
                    datos['apellido_materno'],
                    datos['fecha_nacimiento'],
                    datos['curp'],
                    datos['celular'],
                    datos['email'],
                    datos['estudios']
                ))
                
                conn.commit()
                flash('¡Registro exitoso!', 'success')
                return redirect(url_for('listar_usuarios'))
                
            except Exception as e:
                flash(f'Error al guardar: {str(e)}', 'danger')
            finally:
                if conn:
                    conn.close()
        
        elif 'editar' in request.form:
            return render_template('editar.html', datos=datos)
    
    return render_template('confirmacion.html', datos=datos)

@app.route('/editar', methods=['POST'])
def editar():
    if 'datos_registro' not in session:
        return redirect(url_for('registro'))
    
    # Actualiza los datos en sesión
    session['datos_registro'] = {
        'nombre': request.form['nombre'],
        'apellido_paterno': request.form['apellido_paterno'],
        'apellido_materno': request.form['apellido_materno'],
        'fecha_nacimiento': request.form['fecha_nacimiento'],
        'curp': request.form['curp'],
        'celular': request.form['celular'],
        'email': request.form['email'],
        'estudios': request.form['estudios']
    }
    
    return redirect(url_for('confirmacion'))

@app.route('/usuarios')
def listar_usuarios():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT nombre, apellido_paterno, apellido_materno, 
                   fecha_nacimiento, curp, celular, email, estudios
            FROM usuarios
            ORDER BY apellido_paterno, apellido_materno, nombre
        """)
        
        usuarios = cursor.fetchall()
        return render_template('usuarios.html', usuarios=usuarios)
        
    except Exception as e:
        return f"Error: {str(e)}", 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)