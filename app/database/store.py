from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base

def database(settings):
    path = settings.path(settings.database)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False, 'timeout': 15})
    @event.listens_for(engine, 'connect')
    def setup(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
