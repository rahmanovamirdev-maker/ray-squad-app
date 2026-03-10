# -*- coding: utf-8 -*-
from app import app, db
import sqlalchemy

with app.app_context():
    inspector = sqlalchemy.inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('model_operator_application')]
    print('📋 Столбцы в model_operator_application:', cols)
    print('\n✅ interview_time в базе:', 'interview_time' in cols)
