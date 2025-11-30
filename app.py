import os
import urllib.parse
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# --- App and Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
db_uri = os.environ.get('DATABASE_URL')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-mude-isso-depois'
# Use PostgreSQL on Render, and SQLite locally
if db_uri and db_uri.startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri.replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Hardcoded Admin Credentials ---
# For simplicity, we hardcode the admin credentials.
# For a real application, use a more secure method.
app.config['ADMIN_USERNAME'] = 'admin'
app.config['ADMIN_PASSWORD'] = 'senha123'

db = SQLAlchemy(app)


# --- Database Models ---
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_open = db.Column(db.Boolean, default=False, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    participants = db.relationship('Participant', backref='campaign', lazy=True, cascade="all, delete-orphan")
    def __repr__(self): return f'<Campaign {self.name}>'

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    cpf = db.Column(db.String(14), nullable=False, unique=True)
    address = db.Column(db.String(250), nullable=False)
    address_complement = db.Column(db.String(100), nullable=False, default='') # Added new field
    neighborhood = db.Column(db.String(100), nullable=False, default='') # Added new field
    responsible_full_name = db.Column(db.String(150), nullable=False) # Renamed and made nullable=False
    whatsapp_contact = db.Column(db.String(20), nullable=False)
    how_heard = db.Column(db.String(100), nullable=False, default='Outros') # Added new field
    profession = db.Column(db.String(100), nullable=False, default='Não Informado') # Added new field
    household_members = db.Column(db.Integer, nullable=False, default=1) # Added new field
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    def __repr__(self): return f'<Participant {self.full_name}>'


# --- Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- Routes ---
@app.route("/")
def home():
    # Find all campaigns that are open for registration
    open_campaigns = Campaign.query.filter_by(is_open=True).order_by(Campaign.creation_date.desc()).all()
    return render_template("index.html", campaigns=open_campaigns)

@app.route("/register/<int:campaign_id>", methods=["GET", "POST"])
def register(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, is_open=True).first_or_404()

    if request.method == "POST":
        try:
            birth_date = datetime.strptime(request.form.get("birth_date"), '%Y-%m-%d').date()
            
            # Check if CPF already exists in any campaign
            existing_participant = Participant.query.filter_by(cpf=request.form.get("cpf")).first()
            if existing_participant:
                flash("Este CPF já foi cadastrado em uma de nossas campanhas.", "danger")
                return redirect(url_for("register", campaign_id=campaign.id))

            # Retrieve new fields
            address_complement = request.form.get("address_complement", "")
            neighborhood = request.form.get("neighborhood", "")
            responsible_full_name = request.form.get("responsible_full_name")
            how_heard = request.form.get("how_heard", "Outros")
            profession = request.form.get("profession", "Não Informado")
            
            household_members_str = request.form.get("household_members")
            try:
                household_members = int(household_members_str)
            except (ValueError, TypeError):
                flash("Número de pessoas na casa inválido. Por favor, insira um número inteiro.", "danger")
                return redirect(url_for("register", campaign_id=campaign.id))
            
            new_participant = Participant(
                full_name=request.form.get("full_name"),
                birth_date=birth_date,
                cpf=request.form.get("cpf"),
                address=request.form.get("address"),
                address_complement=address_complement,
                neighborhood=neighborhood,
                responsible_full_name=responsible_full_name,
                whatsapp_contact=request.form.get("whatsapp_contact"),
                how_heard=how_heard,
                profession=profession,
                household_members=household_members,
                campaign_id=campaign.id
            )
            db.session.add(new_participant)
            db.session.commit()
            flash("Inscrição realizada com sucesso! Entraremos em contato.", "success")
            return redirect(url_for("success_page"))
        except Exception as e:
            db.session.rollback()
            # Log the exception for debugging
            app.logger.error(f"Erro ao registrar participante: {e}")
            flash(f"Ocorreu um erro ao processar sua inscrição. Verifique os dados e tente novamente.", "danger")
            return redirect(url_for("register", campaign_id=campaign.id))

    return render_template("register.html", campaign=campaign)

@app.route("/success")
def success_page():
    return render_template("success.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            flash("Login bem-sucedido!", "success")
            return redirect(url_for("admin_panel"))
        else:
            flash("Usuário ou senha inválidos.", "danger")
    return render_template("admin_login.html")

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    flash("Você foi desconectado.", "info")
    return redirect(url_for("home"))

# --- Admin Routes (Protected) ---
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_panel():
    if request.method == "POST":
        campaign_name = request.form.get("campaign_name")
        if campaign_name:
            existing_campaign = Campaign.query.filter_by(name=campaign_name).first()
            if not existing_campaign:
                db.session.add(Campaign(name=campaign_name))
                db.session.commit()
                flash(f"Campanha '{campaign_name}' criada com sucesso!", "success")
            else:
                flash(f"Uma campanha com o nome '{campaign_name}' já existe.", "warning")
        return redirect(url_for("admin_panel"))
    campaigns = Campaign.query.order_by(Campaign.creation_date.desc()).all()
    return render_template("admin.html", campaigns=campaigns)

@app.route("/admin/campaign/<int:campaign_id>/toggle_status", methods=["POST"])
@login_required
def toggle_campaign_status(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    campaign.is_open = not campaign.is_open
    db.session.commit()
    status = "aberta" if campaign.is_open else "fechada"
    flash(f"A campanha '{campaign.name}' foi {status}.", "info")
    return redirect(url_for("admin_panel"))

@app.route("/admin/campaign/<int:campaign_id>", methods=["GET"])
@login_required
def campaign_detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    return render_template("campaign_detail.html", campaign=campaign)

@app.route("/admin/participant/<int:participant_id>/approve", methods=["POST"])
@login_required
def approve_participant(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.is_approved = True
    db.session.commit()
    flash(f"Participante '{participant.full_name}' foi aprovado.", "success")
    return redirect(url_for("campaign_detail", campaign_id=participant.campaign_id))

@app.route("/admin/campaign/<int:campaign_id>/notify", methods=["POST"])
@login_required
def generate_whatsapp_links(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    message_template = request.form.get("message")
    if not message_template:
        flash("O modelo da mensagem não pode estar vazio.", "warning")
        return redirect(url_for("campaign_detail", campaign_id=campaign.id))
    approved_participants = [p for p in campaign.participants if p.is_approved]
    if not approved_participants:
        flash("Não há participantes aprovados para notificar.", "info")
        return redirect(url_for("campaign_detail", campaign_id=campaign.id))
    generated_links = []
    for p in approved_participants:
        personalized_message = message_template.replace("{nome}", p.full_name).replace("{nome_responsavel}", p.responsible_full_name or p.full_name)
        encoded_message = urllib.parse.quote(personalized_message)
        phone_number = ''.join(filter(str.isdigit, p.whatsapp_contact))
        whatsapp_link = f"https://wa.me/55{phone_number}?text={encoded_message}"
        generated_links.append({"name": p.full_name, "link": whatsapp_link})
    return render_template("show_links.html", links=generated_links, campaign=campaign)

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)
