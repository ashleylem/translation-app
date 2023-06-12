from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__= "User"
    id = db.Column(db.String(130), primary_key=True)
    name = db.Column(db.String(120), unique=False, nullable=False)
    username= db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), unique=False, nullable=False)
    
    def __repr__(self):
        return '<User %r>' % self.username

    def serialize(self):
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            # do not serialize the password, its a security breach
        }
        
class Translations(db.Model):
    __tablename__= "Translations"
    id = db.Column(db.String(130), primary_key=True)
    user_id = db.Column(db.String(130), db.ForeignKey('User.id'), nullable=False)
    original_image = db.Column(db.String(130), nullable=True)
    filename = db.Column(db.String(120), unique=False, nullable=True)
    language = db.Column(db.String(120), unique=False, nullable=True)
    
    def __repr__(self): 
        return '<Translations %r>' % self.filename
    
    def serialize(self):return {
        "id": self.id,
        "user_id": self.user_id,
        "image":self.original_image,
        "filename": self.filename,
        "language": self.language,}