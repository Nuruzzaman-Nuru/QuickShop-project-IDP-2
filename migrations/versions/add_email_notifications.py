"""add email notifications

Revision ID: add_email_notifications
Revises: 
Create Date: 2025-05-09

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('user', sa.Column('email_notifications', sa.Boolean(), nullable=True, server_default='1'))

def downgrade():
    op.drop_column('user', 'email_notifications')
