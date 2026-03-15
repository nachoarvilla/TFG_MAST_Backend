from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# The URL uses 'db' because it is the name of the service in docker-compose.yml
SQLALCHEMY_DATABASE_URL = "mysql+mysqlconnector://root:tfgnacho@db:3306/mast_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()