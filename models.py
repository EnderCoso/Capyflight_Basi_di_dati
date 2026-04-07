from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

# Initialize SQLAlchemy
db = SQLAlchemy()

class Aereoporti(db.Model):
    __tablename__ = 'Aereoporti'
    codice_iata = db.Column(db.String(3), primary_key=True)
    nome = db.Column(db.String(20), nullable=False)
    citta = db.Column(db.String(20), nullable=False)
    nazione = db.Column(db.String(20), nullable=False)
    partenza_voli = relationship('Voli', foreign_keys='Voli.partenza_aeroporto', back_populates='partenza_aero')
    arrivo_voli = relationship('Voli', foreign_keys='Voli.arrivo_aeroporto', back_populates='arrivo_aero')

class CompagniaAerea(db.Model):
    __tablename__ = 'compagnia_aerea'
    id_compagnia = db.Column(db.Integer, ForeignKey('Utenti.id_utente'), primary_key=True)
    codice_iata = db.Column(db.String(2), nullable=False)
    nome = db.Column(db.String(30), nullable=False)
    aerei = relationship('Aerei', back_populates='compagnia_rel')
    voli = relationship('Voli', back_populates='compagnia_rel')
    utente = relationship('Utenti', back_populates='compagnia')

class Aerei(db.Model):
    __tablename__ = 'Aerei'
    id_aereo = db.Column(db.Integer, primary_key=True)
    compagnia = db.Column(db.Integer, ForeignKey('compagnia_aerea.id_compagnia'), nullable=False)
    modello = db.Column(db.String(50), nullable=False)
    compagnia_rel = relationship('CompagniaAerea', back_populates='aerei')
    posti = relationship('Posti', back_populates='aereo_rel')
    voli = relationship('Voli', back_populates='aereo_rel')

class Passeggeri(db.Model):
    __tablename__ = 'Passeggeri'
    id_passeggero = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(20), nullable=False)
    cognome = db.Column(db.String(20), nullable=False)
    data_nascita = db.Column(db.Date, nullable=False)
    biglietti = relationship('Biglietti', back_populates='passeggero_rel')

class Posti(db.Model):
    __tablename__ = 'Posti'
    id_posto = db.Column(db.Integer, primary_key=True)
    numero_posto = db.Column(db.String(3), nullable=False)
    tipo_posto = db.Column(db.String(15), nullable=False)
    id_aereo = db.Column(db.Integer, ForeignKey('Aerei.id_aereo'), nullable=False)
    aereo_rel = relationship('Aerei', back_populates='posti')
    biglietti = relationship('Biglietti', back_populates='posto_rel')
    __table_args__ = (
        CheckConstraint("tipo_posto IN ('economy','business','first class')", name='ck_tipo_posto'),
    )

class Voli(db.Model):
    __tablename__ = 'Voli'
    id_volo = db.Column(db.Integer, primary_key=True)
    codice_volo = db.Column(db.String(10), nullable=False)
    id_compagnia = db.Column(db.Integer, ForeignKey('compagnia_aerea.id_compagnia'), nullable=False)
    id_aereo = db.Column(db.Integer, ForeignKey('Aerei.id_aereo'), nullable=False)
    partenza_aeroporto = db.Column(db.String(3), ForeignKey('Aereoporti.codice_iata'), nullable=False)
    arrivo_aeroporto = db.Column(db.String(3), ForeignKey('Aereoporti.codice_iata'), nullable=False)
    prezzo_economy = db.Column(db.Numeric(10,2), nullable=False)
    prezzo_business = db.Column(db.Numeric(10,2), nullable=False)
    prezzo_first = db.Column(db.Numeric(10,2), nullable=False)
    orario_partenza = db.Column(db.DateTime(timezone=True), nullable=False)
    orario_arrivo = db.Column(db.DateTime(timezone=True), nullable=False)
    compagnia_rel = relationship('CompagniaAerea', back_populates='voli')
    aereo_rel = relationship('Aerei', back_populates='voli')
    partenza_aero = relationship('Aereoporti', foreign_keys=[partenza_aeroporto], back_populates='partenza_voli')
    arrivo_aero = relationship('Aereoporti', foreign_keys=[arrivo_aeroporto], back_populates='arrivo_voli')
    biglietti = relationship('Biglietti', back_populates='volo_rel')
    __table_args__ = (
        CheckConstraint('prezzo_economy > 0', name='ck_prezzo_economy_positive'),
        CheckConstraint('prezzo_business > 0', name='ck_prezzo_business_positive'),
        CheckConstraint('prezzo_first > 0', name='ck_prezzo_first_positive'),
    )

class Utenti(db.Model):
    __tablename__ = 'Utenti'
    id_utente = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(30), nullable=False)
    password = db.Column(db.Text, nullable=False)
    user_type = db.Column(db.String(15), nullable=False)
    compagnia = relationship('CompagniaAerea', uselist=False, back_populates='utente')
    __table_args__ = (
        CheckConstraint("user_type IN ('passeggero','compagnia aerea')", name='ck_user_type'),
    )

class Biglietti(db.Model):
    __tablename__ = 'Biglietti'
    id_biglietto = db.Column(db.Integer, primary_key=True)
    id_passeggero = db.Column(db.Integer, ForeignKey('Passeggeri.id_passeggero'), nullable=False)
    id_posto = db.Column(db.Integer, ForeignKey('Posti.id_posto'), nullable=False)
    id_volo = db.Column(db.Integer, ForeignKey('Voli.id_volo'), nullable=False)
    data_acquisto = db.Column(db.DateTime(timezone=True), nullable=False)
    importo_pagato = db.Column(db.Numeric(10,2), nullable=False)
    passeggero_rel = relationship('Passeggeri', back_populates='biglietti')
    posto_rel = relationship('Posti', back_populates='biglietti')
    volo_rel = relationship('Voli', back_populates='biglietti')
    # relazione con Extra
    extra = relationship('Extra', back_populates='biglietto_rel')
    __table_args__ = (
        CheckConstraint('data_acquisto <= CURRENT_TIMESTAMP', name='ck_data_acquisto'),
        CheckConstraint('importo_pagato >= 0', name='ck_importo_pagato_non_negativo'),
        UniqueConstraint('id_volo', 'id_posto', name='uq_biglietto_volo_posto'),
    )

class Extra(db.Model):
    __tablename__ = 'Extra'
    id_extra = db.Column(db.Integer, primary_key=True)
    id_biglietto = db.Column(db.Integer, ForeignKey('Biglietti.id_biglietto'), nullable=False)
    nome = db.Column(db.String(50), nullable=False)
    prezzo = db.Column(db.Numeric(10,2), nullable=False)
    biglietto_rel = relationship('Biglietti', back_populates='extra')
    __table_args__ = (
        CheckConstraint('prezzo > 0', name='ck_extra_prezzo_positive'),
    )
