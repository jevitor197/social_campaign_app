from app import app, db

def create_database():
    """
    This function creates the database and all the necessary tables
    based on the models defined in app.py.
    It should be run once to initialize the database.
    """
    # The 'with app.app_context()' is necessary because the db object
    # needs to know about the application (like the database URI)
    # to do its work.
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created successfully!")
        print("You can find the database file at: social_campaign_app/project.db")

if __name__ == '__main__':
    create_database()

