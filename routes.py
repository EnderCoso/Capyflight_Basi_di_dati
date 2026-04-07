from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from sqlalchemy.orm import aliased, joinedload
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from models import db, Voli, Aereoporti, Aerei, CompagniaAerea, Biglietti, Passeggeri, Utenti, Posti, Extra
from urllib.parse import urlparse, parse_qs

bp = Blueprint('main', __name__)

# Catalogo extra disponibile
EXTRA_CATALOGO = [
    { 'code': 'bag10', 'nome': 'Valigia 10kg', 'prezzo': Decimal('15.00') },
    { 'code': 'bag20', 'nome': 'Valigia 20kg', 'prezzo': Decimal('30.00') },
]

@bp.route('/')
def home():
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    tickets = []
    company_stats = []
    voli = []

    if user_id and user_type == 'passeggero':
        tickets = Biglietti.query.filter_by(id_passeggero=user_id).all()
    elif user_id and user_type == 'compagnia aerea':
        # Per le compagnie aeree, mostra le statistiche dei loro voli
        try:
            # L'ID compagnia corrisponde all'ID utente
            company_id = user_id
            company_stats = (
                db.session.query(
                    Voli.codice_volo,
                    func.count(Biglietti.id_biglietto).label('num_biglietti'),
                    func.sum(Biglietti.importo_pagato).label('ricavi_totali'),
                    Voli.prezzo_economy,
                    Voli.prezzo_business,
                    Voli.prezzo_first
                )
                .filter(Voli.id_compagnia == company_id)
                .outerjoin(Biglietti, Biglietti.id_volo == Voli.id_volo)
                .group_by(Voli.id_volo, Voli.codice_volo, Voli.prezzo_economy, Voli.prezzo_business, Voli.prezzo_first)
                .all()
            )
        except Exception as e:
            print(f"Errore durante le statistiche compagnia: {e}")
            company_stats = []
    else:
        # Per utenti non loggati o di tipo non gestito, mostra tutti i voli
        voli = Voli.query.all()

    # Passa la data di oggi per precompilare/min nel date picker
    try:
        from datetime import date
        today_str = date.today().isoformat()
    except Exception:
        today_str = None

    return render_template('home.html', tickets=tickets, company_stats=company_stats, user_type=user_type, today_str=today_str, voli=voli)

@bp.route('/voli')
def lista_voli():
    from datetime import datetime, timedelta, timezone

    # Parametri di ricerca
    partenza = request.args.get('partenza', '').strip()
    arrivo = request.args.get('arrivo', '').strip()
    data_str = request.args.get('data', '').strip()
    sort_by = request.args.get('sort', '')

    # Gestione date
    data_inizio = data_fine = data_fine_display = None
    if data_str:
        try:
            dt_start = datetime.strptime(data_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            dt_end = dt_start + timedelta(days=7)
            data_inizio, data_fine = dt_start, dt_end
            data_fine_display = dt_end - timedelta(days=1)
        except ValueError:
            data_str = None  # Ignora data non valida

    voli_combinati = []

    #Nessun filtro -> mostra tutti i voli
    if not (partenza or arrivo or data_inizio):
        all_voli = Voli.query.options(
            joinedload(Voli.compagnia_rel),
            joinedload(Voli.aereo_rel),
            joinedload(Voli.partenza_aero),
            joinedload(Voli.arrivo_aero)
        ).all()
        for v in all_voli:
            voli_combinati.append({
                'type': 'direct',
                'flight_info': (
                    v,
                    (v.compagnia_rel.nome if v.compagnia_rel else ''),
                    (v.aereo_rel.modello if v.aereo_rel else ''),
                    (v.partenza_aero.nome if v.partenza_aero else v.partenza_aeroporto),
                    (v.partenza_aero.citta if v.partenza_aero else ''),
                    (v.arrivo_aero.nome if v.arrivo_aero else v.arrivo_aeroporto),
                    (v.arrivo_aero.citta if v.arrivo_aero else '')
                )
            })
    else:
        #Se presenti filtri -> usa la query con join per filtrare
        part_direct = aliased(Aereoporti)
        arr_direct = aliased(Aereoporti)
        query_diretti = db.session.query(
            Voli, CompagniaAerea.nome.label('nome_compagnia'), Aerei.modello.label('modello_aereo'),
            part_direct.nome.label('nome_partenza'), part_direct.citta.label('citta_partenza'),
            arr_direct.nome.label('nome_arrivo'), arr_direct.citta.label('citta_arrivo')
        ).join(CompagniaAerea, Voli.id_compagnia == CompagniaAerea.id_compagnia)\
         .join(Aerei, Voli.id_aereo == Aerei.id_aereo)\
         .join(part_direct, Voli.partenza_aeroporto == part_direct.codice_iata)\
         .join(arr_direct, Voli.arrivo_aeroporto == arr_direct.codice_iata)

        if partenza:
            query_diretti = query_diretti.filter(part_direct.citta.ilike(f"%{partenza}%"))
        if arrivo:
            query_diretti = query_diretti.filter(arr_direct.citta.ilike(f"%{arrivo}%"))
        if data_inizio:
            query_diretti = query_diretti.filter(Voli.orario_partenza.between(data_inizio, data_fine))

        voli_diretti_raw = query_diretti.all()
        voli_combinati = [{'type': 'direct', 'flight_info': volo} for volo in voli_diretti_raw]

        # Voli con scalo (solo se entrambi i filtri città sono presenti)
        if partenza and arrivo:
            Volo1 = aliased(Voli, name='volo1')
            Volo2 = aliased(Voli, name='volo2')
            AeroportoP = aliased(Aereoporti, name='aeroporto_p')
            AeroportoS = aliased(Aereoporti, name='aeroporto_s')
            AeroportoA = aliased(Aereoporti, name='aeroporto_a')
            Compagnia1 = aliased(CompagniaAerea, name='compagnia1')
            Compagnia2 = aliased(CompagniaAerea, name='compagnia2')

            query_scalo = db.session.query(
                Volo1, Volo2,
                Compagnia1.nome.label('compagnia1_nome'), Compagnia2.nome.label('compagnia2_nome'),
                AeroportoP.citta.label('partenza_citta'), AeroportoS.citta.label('scalo_citta'),
                AeroportoA.citta.label('arrivo_citta')
            ).select_from(Volo1).join(Volo2, Volo1.arrivo_aeroporto == Volo2.partenza_aeroporto)\
                .join(AeroportoP, Volo1.partenza_aeroporto == AeroportoP.codice_iata)\
                .join(AeroportoA, Volo2.arrivo_aeroporto == AeroportoA.codice_iata)\
                .join(AeroportoS, Volo1.arrivo_aeroporto == AeroportoS.codice_iata)\
                .join(Compagnia1, Volo1.id_compagnia == Compagnia1.id_compagnia)\
                .join(Compagnia2, Volo2.id_compagnia == Compagnia2.id_compagnia)\
                .filter(AeroportoP.citta.ilike(f"%{partenza}%"))\
                .filter(AeroportoA.citta.ilike(f"%{arrivo}%"))

            if data_inizio:
                query_scalo = query_scalo.filter(Volo1.orario_partenza.between(data_inizio, data_fine))

            voli_con_scalo_raw = query_scalo.all()

            from datetime import timedelta as _td
            for v1, v2, comp1, comp2, citta_p, citta_s, citta_a in voli_con_scalo_raw:
                layover = v2.orario_partenza - v1.orario_arrivo
                if _td(hours=2) <= layover <= _td(hours=10):
                    voli_combinati.append({
                        'type': 'connection',
                        'flight1_info': (v1, comp1, None, None, citta_p, None, citta_s),
                        'flight2_info': (v2, comp2, None, None, citta_s, None, citta_a),
                        'layover': layover,
                        'total_price': v1.prezzo_economy + v2.prezzo_economy,
                        'total_duration': (v2.orario_arrivo - v1.orario_partenza)
                    })

    #Ordinamento
    if sort_by:
        def sort_key(volo):
            if volo['type'] == 'direct':
                if sort_by == 'price': return volo['flight_info'][0].prezzo_economy
                if sort_by == 'duration': return volo['flight_info'][0].orario_arrivo - volo['flight_info'][0].orario_partenza
            else:
                if sort_by == 'price': return volo['total_price']
                if sort_by == 'duration': return volo['total_duration']
            return 0
        voli_combinati.sort(key=sort_key)


    return render_template(
        'lista_voli.html',
        voli=voli_combinati,
        citta_partenza=partenza,
        citta_arrivo=arrivo,
        data_query=data_str,
        data_inizio=data_inizio,
        data_fine_display=data_fine_display,
        sort_by=sort_by
    )


@bp.route('/aeroporti')
def lista_aeroporti():
    try:
        aeroporti = Aereoporti.query.all()
    except Exception as e:
        print(f"Errore durante la query aeroporti: {e}")
        aeroporti = []
    return render_template('lista_aeroporti.html', aeroporti=aeroporti)

@bp.route('/compagnie')
def lista_compagnie():
    try:
        compagnie = CompagniaAerea.query.all()
    except Exception as e:
        print(f"Errore durante la query compagnie: {e}")
        compagnie = []
    return render_template('lista_compagnie.html', compagnie=compagnia)

@bp.route('/api/voli')
def api_voli():
    """API endpoint per ottenere la lista dei voli in formato JSON"""
    try:
        voli = Voli.query.all()
        voli_data = []
        for volo in voli:
            voli_data.append({
                'id_volo': volo.id_volo,
                'codice_volo': volo.codice_volo,
                'partenza': volo.partenza_aeroporto,
                'arrivo': volo.arrivo_aeroporto,
                'prezzo_economy': float(volo.prezzo_economy),
                'prezzo_business': float(volo.prezzo_business),
                'prezzo_first': float(volo.prezzo_first),
                'orario_partenza': volo.orario_partenza.isoformat(),
                'orario_arrivo': volo.orario_arrivo.isoformat()
            })
        return jsonify(voli_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/statistiche')
def statistiche():
    if not session.get('user_id') or session.get('user_type') != 'compagnia aerea':
        flash('Accesso non autorizzato.')
        return redirect(url_for('main.login'))

    user_id = session.get('user_id')
    company_id = user_id
    compagnia = CompagniaAerea.query.get(company_id)

    if not compagnia:
        flash('Compagnia non trovata.')
        return redirect(url_for('main.home'))

    # Controlla se ci sono voli prima di procedere
    # Verifica esistenza di almeno un volo per la compagnia
    has_flights = db.session.query(Voli.id_volo).filter(Voli.id_compagnia == company_id).first() is not None

    statistiche = {
        'voli_totali': 0,
        'passeggeri_totali': 0,
        'ricavi_totali': Decimal('0.00'),
        'tratta_piu_presente': "N/A"
    }
    voli_stats = []

    if has_flights:
        try:
            # Statistiche aggregate
            statistiche['voli_totali'] = db.session.query(func.count(Voli.id_volo)).filter(Voli.id_compagnia == company_id).scalar() or 0

            statistiche['passeggeri_totali'] = db.session.query(func.count(Biglietti.id_biglietto))\
                .join(Voli, Biglietti.id_volo == Voli.id_volo)\
                .filter(Voli.id_compagnia == company_id).scalar() or 0

            ricavi = db.session.query(func.sum(Biglietti.importo_pagato))\
                .join(Voli, Biglietti.id_volo == Voli.id_volo)\
                .filter(Voli.id_compagnia == company_id).scalar()
            statistiche['ricavi_totali'] = ricavi if ricavi is not None else Decimal('0.00')

            # Tratta più presente
            part_alias = aliased(Aereoporti)
            arr_alias = aliased(Aereoporti)
            tratta_query = db.session.query(
                part_alias.citta.label('partenza'),
                arr_alias.citta.label('arrivo'),
                func.count(Voli.id_volo).label('conteggio')
            ).join(part_alias, Voli.partenza_aeroporto == part_alias.codice_iata)\
             .join(arr_alias, Voli.arrivo_aeroporto == arr_alias.codice_iata)\
             .filter(Voli.id_compagnia == company_id)\
             .group_by(part_alias.citta, arr_alias.citta)\
             .order_by(func.count(Voli.id_volo).desc())\
             .first()

            if tratta_query:
                statistiche['tratta_piu_presente'] = f"{tratta_query.partenza} -> {tratta_query.arrivo}"

            # Statistiche dettagliate per volo
            voli_stats = db.session.query(
                Voli.codice_volo,
                Voli.orario_partenza,
                Voli.orario_arrivo,
                func.count(Biglietti.id_biglietto).label('biglietti_venduti'),
                func.coalesce(func.sum(Biglietti.importo_pagato), Decimal('0.00')).label('ricavi_totali')
            ).outerjoin(Biglietti, Voli.id_volo == Biglietti.id_volo)\
             .filter(Voli.id_compagnia == company_id)\
             .group_by(Voli.id_volo, Voli.codice_volo, Voli.orario_partenza, Voli.orario_arrivo)\
             .order_by(Voli.orario_partenza.desc())\
             .all()

        except Exception as e:
            print(f"Errore statistiche: {e}")
            flash('Errore nel caricamento delle statistiche.')

    return render_template(
        'statistiche.html',
        nome_compagnia=compagnia.nome,
        statistiche=statistiche,
        voli_stats=voli_stats
    )


# Aggiunta login/logout e pagina profilo
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = Utenti.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id_utente
            session['user_type'] = user.user_type
            return redirect(url_for('main.home'))  # Reindirizza alla home invece del profilo
        flash('Credenziali errate, riprova')
        return redirect(url_for('main.login'))
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))

@bp.route('/profilo')
def profilo():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    # Controlli di base
    if not user_id or not user_type:
        return redirect(url_for('main.login'))

    try:
        user = Utenti.query.get(user_id)
        if not user:
            session.clear()
            return redirect(url_for('main.login'))

        nome = cognome = None
        tickets = []
        company_stats = []
        company_name = None
        passeggero = None

        if user_type == 'passeggero':
            try:
                passeggero = Passeggeri.query.get(user_id)
                if passeggero:
                    nome = passeggero.nome
                    cognome = passeggero.cognome
                    tickets = Biglietti.query.filter_by(id_passeggero=user_id).all()
            except Exception as e:
                print(f"Errore nel caricamento dati passeggero: {e}")

        elif user_type == 'compagnia aerea':
            try:
                # L'ID compagnia corrisponde all'ID utente
                company_id = user_id
                compagnia = CompagniaAerea.query.get(company_id)
                if compagnia:
                    company_name = compagnia.nome
                    # Query con gestione dei valori NULL
                    raw_stats = (
                        db.session.query(
                            Voli.codice_volo,
                            func.count(Biglietti.id_biglietto).label('num_biglietti'),
                            func.coalesce(func.sum(Biglietti.importo_pagato), 0).label('ricavi_totali'),
                            Voli.prezzo_economy,
                            Voli.prezzo_business,
                            Voli.prezzo_first
                        )
                        .filter(Voli.id_compagnia == company_id)
                        .outerjoin(Biglietti, Biglietti.id_volo == Voli.id_volo)
                        .group_by(Voli.id_volo, Voli.codice_volo, Voli.prezzo_economy, Voli.prezzo_business, Voli.prezzo_first)
                        .all()
                    )

                    # Processa i risultati assicurandosi che non ci siano valori None
                    company_stats = []
                    for stat in raw_stats:
                        company_stats.append({
                            'codice_volo': stat.codice_volo,
                            'num_biglietti': stat.num_biglietti or 0,
                            'ricavi_totali': float(stat.ricavi_totali or 0),
                            'prezzo_economy': float(stat.prezzo_economy or 0),
                            'prezzo_business': float(stat.prezzo_business or 0),
                            'prezzo_first': float(stat.prezzo_first or 0)
                        })
                else:
                    print(f"Compagnia non trovata per ID {company_id}")
            except Exception as e:
                print(f"Errore nel caricamento dati compagnia: {e}")

    except Exception as e:
        print(f"Errore generale nella route profilo: {e}")
        return "Errore nel caricamento del profilo", 500

    return render_template('profilo.html', user=user, passeggero=passeggero, nome=nome, cognome=cognome, tickets=tickets,
                         company_stats=company_stats, company_name=company_name, user_type=user_type)

@bp.route('/voli/<int:id_volo>')
def dettaglio_volo(id_volo):
    try:
        # Query per ottenere tutte le informazioni del volo
        part = aliased(Aereoporti)
        arr = aliased(Aereoporti)
        volo_data = db.session.query(
            Voli,
            CompagniaAerea.nome.label('nome_compagnia'),
            Aerei.modello.label('modello_aereo'),
            part.nome.label('nome_partenza'),
            part.citta.label('citta_partenza'),
            arr.nome.label('nome_arrivo'),
            arr.citta.label('citta_arrivo')
        ).join(
            CompagniaAerea, Voli.id_compagnia == CompagniaAerea.id_compagnia
        ).join(
            Aerei, Voli.id_aereo == Aerei.id_aereo
        ).join(
            part, Voli.partenza_aeroporto == part.codice_iata
        ).join(
            arr, Voli.arrivo_aeroporto == arr.codice_iata
        ).filter(
            Voli.id_volo == id_volo
        ).first()

        if not volo_data:
            return "Volo non trovato", 404

        volo, nome_compagnia, modello_aereo, nome_partenza, citta_partenza, nome_arrivo, citta_arrivo = volo_data

        # Conta i posti disponibili per ogni classe
        posti_stats = db.session.query(
            Posti.tipo_posto,
            func.count(Posti.id_posto).label('totali'),
            func.count(Biglietti.id_biglietto).label('occupati')
        ).join(
            Aerei, Posti.id_aereo == Aerei.id_aereo
        ).outerjoin(
            Biglietti,
            and_(Biglietti.id_posto == Posti.id_posto, Biglietti.id_volo == id_volo)
        ).filter(
            Aerei.id_aereo == volo.id_aereo
        ).group_by(Posti.tipo_posto).all()

        # Organizza i dati dei posti
        posti_disponibili = {}
        for tipo_posto, totali, occupati in posti_stats:
            disponibili = totali - occupati
            posti_disponibili[tipo_posto] = {
                'totali': totali,
                'occupati': occupati,
                'disponibili': disponibili
            }

    except Exception as e:
        print(f"Errore durante la query dettaglio volo: {e}")
        return "Errore nel caricamento dei dati", 500

    return render_template('dettaglio_volo.html',
                         volo=volo,
                         nome_compagnia=nome_compagnia,
                         modello_aereo=modello_aereo,
                         nome_partenza=nome_partenza,
                         citta_partenza=citta_partenza,
                         nome_arrivo=nome_arrivo,
                         citta_arrivo=citta_arrivo,
                         posti_disponibili=posti_disponibili)

@bp.route('/volo/<int:id_volo>/posti')
def selezione_posti(id_volo):
    # Verifica che l'utente sia loggato come passeggero
    if not session.get('user_id') or session.get('user_type') != 'passeggero':
        flash('Devi essere loggato come passeggero per selezionare i posti')
        return redirect(url_for('main.login'))

    try:
        # Query per ottenere informazioni del volo
        part = aliased(Aereoporti)
        arr = aliased(Aereoporti)
        volo_data = db.session.query(
            Voli,
            CompagniaAerea.nome.label('nome_compagnia'),
            Aerei.modello.label('modello_aereo'),
            part.nome.label('nome_partenza'),
            part.citta.label('citta_partenza'),
            arr.nome.label('nome_arrivo'),
            arr.citta.label('citta_arrivo')
        ).join(
            CompagniaAerea, Voli.id_compagnia == CompagniaAerea.id_compagnia
        ).join(
            Aerei, Voli.id_aereo == Aerei.id_aereo
        ).join(
            part, Voli.partenza_aeroporto == part.codice_iata
        ).join(
            arr, Voli.arrivo_aeroporto == arr.codice_iata
        ).filter(
            Voli.id_volo == id_volo
        ).first()

        if not volo_data:
            return "Volo non trovato", 404

        volo, nome_compagnia, modello_aereo, nome_partenza, citta_partenza, nome_arrivo, citta_arrivo = volo_data

        # Query per ottenere tutti i posti dell'aereo con informazioni su occupazione
        posti_query = db.session.query(
            Posti.id_posto,
            Posti.numero_posto,
            Posti.tipo_posto,
            Biglietti.id_biglietto
        ).outerjoin(
            Biglietti,
            and_(Biglietti.id_posto == Posti.id_posto, Biglietti.id_volo == id_volo)
        ).filter(
            Posti.id_aereo == volo.id_aereo
        ).order_by(Posti.numero_posto).all()

        # Organizza i posti per tipo e aggiunge informazioni su disponibilità
        posti_per_tipo = {}
        for posto in posti_query:
            id_posto, numero_posto, tipo_posto, biglietto_id = posto
            if tipo_posto not in posti_per_tipo:
                posti_per_tipo[tipo_posto] = []

            posti_per_tipo[tipo_posto].append({
                'id_posto': id_posto,
                'numero_posto': numero_posto,
                'occupato': biglietto_id is not None
            })

    except Exception as e:
        print(f"Errore durante la query selezione posti: {e}")
        return "Errore nel caricamento dei posti", 500

    return render_template('selezione_posti.html',
                         volo=volo,
                         nome_compagnia=nome_compagnia,
                         modello_aereo=modello_aereo,
                         citta_partenza=citta_partenza,
                         citta_arrivo=citta_arrivo,
                         posti_per_tipo=posti_per_tipo)

@bp.route('/volo/<int:id_volo>/prenota/<int:id_posto>', methods=['POST', 'OPTIONS'])
def prenota_posto(id_volo, id_posto):
    # Gestisci richieste OPTIONS per CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response

    print(f"=== PRENOTAZIONE AVVIATA ===")
    print(f"ID Volo: {id_volo}, ID Posto: {id_posto}")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Session: {dict(session)}")

    # Verifica che l'utente sia loggato come passeggero
    if not session.get('user_id') or session.get('user_type') != 'passeggero':
        print("ERRORE: Utente non autorizzato")
        response = jsonify({'error': 'Accesso non autorizzato'})
        response.status_code = 403
        response.headers['Content-Type'] = 'application/json'
        return response

    try:
        user_id = session.get('user_id')
        passeggero = Passeggeri.query.get(user_id)
        if not passeggero:
            response = jsonify({'error': 'Passeggero non trovato'})
            response.status_code = 404
            response.headers['Content-Type'] = 'application/json'
            return response

        # Verifica che il posto non sia già occupato
        biglietto_esistente = Biglietti.query.filter_by(
            id_volo=id_volo,
            id_posto=id_posto
        ).first()
        if biglietto_esistente:
            response = jsonify({'error': 'Posto già occupato'})
            response.status_code = 400
            response.headers['Content-Type'] = 'application/json'
            return response

        # Ottieni informazioni sul posto e volo per calcolare il prezzo
        posto = Posti.query.get(id_posto)
        volo = Voli.query.get(id_volo)
        if not posto or not volo:
            response = jsonify({'error': 'Posto o volo non trovato'})
            response.status_code = 404
            response.headers['Content-Type'] = 'application/json'
            return response

        # Verifica coerenza posto/volo (stesso aereo)
        if posto.id_aereo != volo.id_aereo:
            response = jsonify({'error': 'Posto non valido per questo volo'})
            response.status_code = 400
            response.headers['Content-Type'] = 'application/json'
            return response

        # Calcola prezzo
        if posto.tipo_posto == 'economy':
            prezzo = volo.prezzo_economy
        elif posto.tipo_posto == 'business':
            prezzo = volo.prezzo_business
        elif posto.tipo_posto == 'first class':
            prezzo = volo.prezzo_first
        else:
            response = jsonify({'error': 'Tipo posto non valido'})
            response.status_code = 400
            response.headers['Content-Type'] = 'application/json'
            return response

        nuovo_biglietto = Biglietti(
            id_passeggero=user_id,
            id_posto=id_posto,
            id_volo=id_volo,
            data_acquisto=db.func.now(),
            importo_pagato=prezzo
        )
        db.session.add(nuovo_biglietto)
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            cn = getattr(getattr(e, 'orig', None), 'diag', None)
            cname = getattr(cn, 'constraint_name', None)
            if cname == 'uq_biglietto_volo_posto' or 'uq_biglietto_volo_posto' in str(getattr(e, 'orig', '')):
                response = jsonify({'error': 'Posto già occupato'})
                response.status_code = 400
            else:
                response = jsonify({'error': 'Errore di integrità durante la prenotazione'})
                response.status_code = 400
            response.headers['Content-Type'] = 'application/json'
            return response

        response = jsonify({'success': True, 'message': f'Posto {posto.numero_posto} prenotato con successo!', 'prezzo': float(prezzo)})
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        db.session.rollback()

        response = jsonify({'error': f'Errore durante la prenotazione: {str(e)}'})
        response.status_code = 500
        response.headers['Content-Type'] = 'application/json'
        return response

@bp.route('/compagnia/voli/nuovo', methods=['GET', 'POST'])
def aggiungi_volo():
    # Solo utenti compagnia aerea
    if not session.get('user_id') or session.get('user_type') != 'compagnia aerea':
        flash('Devi essere loggato come compagnia aerea per aggiungere un volo')
        return redirect(url_for('main.login'))

    try:
        user_id = session.get('user_id')
        # L'ID compagnia corrisponde all'ID utente
        company_id = user_id
        compagnia = CompagniaAerea.query.get(company_id)
        if not compagnia:
            flash('Compagnia non trovata per il tuo account')
            return redirect(url_for('main.home'))

        # Aerei della compagnia e lista aeroporti
        aerei = Aerei.query.filter_by(compagnia=company_id).all()
        aeroporti = Aereoporti.query.order_by(Aereoporti.codice_iata.asc()).all()

        if request.method == 'GET':
            return render_template('aggiungi_volo.html', compagnia=compagnia, aerei=aerei, aeroporti=aeroporti)

        # POST: crea il volo
        codice_volo = request.form.get('codice_volo', '').strip()
        id_aereo = request.form.get('id_aereo')
        partenza_aeroporto = request.form.get('partenza_aeroporto')
        arrivo_aeroporto = request.form.get('arrivo_aeroporto')
        prezzo_economy = request.form.get('prezzo_economy')
        prezzo_business = request.form.get('prezzo_business')
        prezzo_first = request.form.get('prezzo_first')
        orario_partenza = request.form.get('orario_partenza')
        orario_arrivo = request.form.get('orario_arrivo')

        errors = []
        if not codice_volo:
            errors.append('Codice volo obbligatorio')
        try:
            id_aereo = int(id_aereo)
        except (TypeError, ValueError):
            errors.append('Aereo non valido')
        if not partenza_aeroporto or not arrivo_aeroporto:
            errors.append('Seleziona aeroporti di partenza e arrivo')
        try:
            from decimal import Decimal
            pe = Decimal(prezzo_economy)
            pb = Decimal(prezzo_business)
            pf = Decimal(prezzo_first)
            if pe <= 0 or pb <= 0 or pf <= 0:
                errors.append('I prezzi devono essere maggiori di 0')
        except Exception:
            errors.append('Prezzi non validi')
        try:
            from datetime import datetime, timezone
            dtp = datetime.strptime(orario_partenza, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
            dta = datetime.strptime(orario_arrivo, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
            if dta <= dtp:
                errors.append('L\'orario di arrivo deve essere successivo alla partenza')
        except Exception:
            errors.append('Formati data/ora non validi')

        # Validazioni su FK
        aereo = Aerei.query.get(id_aereo) if isinstance(id_aereo, int) else None
        if not aereo or aereo.compagnia != company_id:
            errors.append('Aereo selezionato non valido per la tua compagnia')
        if not Aereoporti.query.get(partenza_aeroporto):
            errors.append('Aeroporto di partenza non valido')
        if not Aereoporti.query.get(arrivo_aeroporto):
            errors.append('Aeroporto di arrivo non valido')
        if partenza_aeroporto == arrivo_aeroporto:
            errors.append('Partenza e arrivo non possono coincidere')

        if errors:
            for e in errors:
                flash(e)
            return render_template('aggiungi_volo.html', compagnia=compagnia, aerei=aerei, aeroporti=aeroporti,
                                   form=request.form), 400

        # Creazione volo
        nuovo_volo = Voli(
            codice_volo=codice_volo,
            id_compagnia=company_id,
            id_aereo=id_aereo,
            partenza_aeroporto=partenza_aeroporto,
            arrivo_aeroporto=arrivo_aeroporto,
            prezzo_economy=pe,
            prezzo_business=pb,
            prezzo_first=pf,
            orario_partenza=dtp,
            orario_arrivo=dta
        )
        db.session.add(nuovo_volo)
        db.session.commit()

        flash('Volo creato con successo')
        return redirect(url_for('main.dettaglio_volo', id_volo=nuovo_volo.id_volo))

    except Exception as e:
        db.session.rollback()
        print(f"Errore creazione volo: {e}")
        flash(f'Errore durante la creazione del volo: {e}')
        return redirect(url_for('main.home'))

@bp.route('/volo/<int:id_volo>/prenota', methods=['POST'])
def prenota_posto_form(id_volo):
    # Solo passeggero
    if not session.get('user_id') or session.get('user_type') != 'passeggero':
        flash('Devi essere loggato come passeggero per prenotare')
        return redirect(url_for('main.login'))

    user_id = session.get('user_id')

    try:
        # Recupera volo e id_posto dal form
        id_posto_raw = request.form.get('id_posto')
        try:
            id_posto = int(id_posto_raw)
        except (TypeError, ValueError):
            flash('Selezione posto non valida')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        passeggero = Passeggeri.query.get(user_id)
        if not passeggero:
            flash('Passeggero non trovato')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        volo = Voli.query.get(id_volo)
        posto = Posti.query.get(id_posto)
        if not volo or not posto:
            flash('Posto o volo non trovato')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        if posto.id_aereo != volo.id_aereo:
            flash('Posto non valido per questo volo')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Prezzo
        if posto.tipo_posto == 'economy':
            prezzo = volo.prezzo_economy
        elif posto.tipo_posto == 'business':
            prezzo = volo.prezzo_business
        elif posto.tipo_posto == 'first class':
            prezzo = volo.prezzo_first
        else:
            flash('Tipo posto non valido')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        biglietto = Biglietti(
            id_passeggero=user_id,
            id_posto=id_posto,
            id_volo=id_volo,
            data_acquisto=db.func.now(),
            importo_pagato=prezzo
        )
        db.session.add(biglietto)
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            cn = getattr(getattr(e, 'orig', None), 'diag', None)
            cname = getattr(cn, 'constraint_name', None)
            if cname == 'uq_biglietto_volo_posto' or 'uq_biglietto_volo_posto' in str(getattr(e, 'orig', '')):
                flash('Questo posto è già occupato')
            else:
                flash('Errore di integrità durante la prenotazione')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        flash(f'Prenotazione completata. Posto {posto.numero_posto} acquistato.')
        return redirect(url_for('main.profilo'))

    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la prenotazione: {e}')
        return redirect(url_for('main.selezione_posti', id_volo=id_volo))

@bp.route('/volo/<int:id_volo>/extra', methods=['GET', 'POST'])
def scegli_extra(id_volo):
    # Solo passeggero
    if not session.get('user_id') or session.get('user_type') != 'passeggero':
        flash('Devi essere loggato come passeggero per continuare')
        return redirect(url_for('main.login'))

    try:
        user_id = session.get('user_id')
        passeggero = Passeggeri.query.get(user_id)
        if not passeggero:
            flash('Passeggero non trovato')
            return redirect(url_for('main.lista_voli'))

        id_posto_raw = request.form.get('id_posto') if request.method == 'POST' else request.args.get('id_posto')
        try:
            id_posto = int(id_posto_raw)
        except (TypeError, ValueError):
            flash('Selezione posto non valida')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        volo = Voli.query.get(id_volo)
        posto = Posti.query.get(id_posto)
        if not volo or not posto:
            flash('Posto o volo non trovato')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))
        if posto.id_aereo != volo.id_aereo:
            flash('Posto non valido per questo volo')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Calcola prezzo base
        if posto.tipo_posto == 'economy':
            prezzo_base = volo.prezzo_economy
            classe_nome = 'Economy'
        elif posto.tipo_posto == 'business':
            prezzo_base = volo.prezzo_business
            classe_nome = 'Business'
        elif posto.tipo_posto == 'first class':
            prezzo_base = volo.prezzo_first
            classe_nome = 'First Class'
        else:
            flash('Tipo posto non valido')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Verifica che il posto non sia già occupato per questo volo
        if Biglietti.query.filter_by(id_volo=id_volo, id_posto=id_posto).first():
            flash('Questo posto è già occupato')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Converte i prezzi del catalogo in float per il template
        extra_catalogo_view = [{**e, 'prezzo': float(e['prezzo'])} for e in EXTRA_CATALOGO]

        return render_template(
            'scegli_extra.html',
            volo=volo,
            posto=posto,
            classe_nome=classe_nome,
            prezzo_base=float(prezzo_base),
            extra_catalogo=extra_catalogo_view
        )

    except Exception as e:
        flash(f'Errore nel caricamento degli extra: {e}')
        return redirect(url_for('main.selezione_posti', id_volo=id_volo))

@bp.route('/volo/<int:id_volo>/conferma', methods=['POST'])
def conferma_prenotazione(id_volo):
    # Solo passeggero
    if not session.get('user_id') or session.get('user_type') != 'passeggero':
        flash('Devi essere loggato come passeggero per confermare')
        return redirect(url_for('main.login'))

    user_id = session.get('user_id')

    try:
        id_posto_raw = request.form.get('id_posto')
        try:
            id_posto = int(id_posto_raw)
        except (TypeError, ValueError):
            flash('Selezione posto non valida')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Recupera volo/posto e validazioni
        volo = Voli.query.get(id_volo)
        posto = Posti.query.get(id_posto)
        if not volo or not posto:
            flash('Posto o volo non trovato')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))
        if posto.id_aereo != volo.id_aereo:
            flash('Posto non valido per questo volo')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Prezzo base
        if posto.tipo_posto == 'economy':
            prezzo_base = volo.prezzo_economy
        elif posto.tipo_posto == 'business':
            prezzo_base = volo.prezzo_business
        elif posto.tipo_posto == 'first class':
            prezzo_base = volo.prezzo_first
        else:
            flash('Tipo posto non valido')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Somma extra selezionati
        codes_selezionati = request.form.getlist('extras')
        by_code = {e['code']: e for e in EXTRA_CATALOGO}
        totale_extra = Decimal('0.00')
        for code in codes_selezionati:
            item = by_code.get(code)
            if item:
                totale_extra += item['prezzo']

        importo_totale = Decimal(str(prezzo_base)) + totale_extra

        # Controllo disponibilità prima della creazione (ulteriore rispetto a scegli_extra)
        if Biglietti.query.filter_by(id_volo=id_volo, id_posto=id_posto).first():
            flash('Questo posto è già occupato')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Crea biglietto (concorrenza gestita anche dal vincolo unico a DB)
        biglietto = Biglietti(
            id_passeggero=user_id,
            id_posto=id_posto,
            id_volo=id_volo,
            data_acquisto=db.func.now(),
            importo_pagato=importo_totale
        )
        db.session.add(biglietto)
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            cn = getattr(getattr(e, 'orig', None), 'diag', None)
            cname = getattr(cn, 'constraint_name', None)
            if cname == 'uq_biglietto_volo_posto' or 'uq_biglietto_volo_posto' in str(getattr(e, 'orig', '')):
                flash('Questo posto è già occupato')
            else:
                flash('Errore di integrità durante la prenotazione')
            return redirect(url_for('main.selezione_posti', id_volo=id_volo))

        # Inserisci eventuali extra selezionati legati al biglietto
        if codes_selezionati:
            for code in codes_selezionati:
                item = by_code.get(code)
                if not item:
                    continue
                db.session.add(Extra(id_biglietto=biglietto.id_biglietto, nome=item['nome'], prezzo=item['prezzo']))
            db.session.commit()

        flash(f'Prenotazione completata. Posto {posto.numero_posto} acquistato.')
        return redirect(url_for('main.profilo'))

    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la conferma: {e}')
        return redirect(url_for('main.selezione_posti', id_volo=id_volo))

@bp.route('/video')
def video():
    # URL video predefinito
    default_url = 'https://www.youtube.com/watch?v=vOeliQfjUzA'
    url = (request.args.get('url', '').strip() or default_url)
    provider = None
    embed_url = None

    if url:
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = parsed.path
            query = parsed.query

            # YouTube
            if 'youtube.com' in host or 'youtu.be' in host:
                video_id = None
                if 'youtu.be' in host:
                    video_id = path.lstrip('/').split('?')[0]
                elif 'youtube.com' in host:
                    if path.startswith('/watch'):
                        q = parse_qs(query)
                        video_id = (q.get('v') or [None])[0]
                    elif path.startswith('/embed/'):
                        video_id = path.split('/embed/')[1].split('/')[0]
                if video_id:
                    provider = 'youtube'
                    embed_url = f"https://www.youtube.com/embed/{video_id}"

            # Vimeo
            if not embed_url and 'vimeo.com' in host:
                # path like /123456789
                vimeo_id = path.strip('/').split('/')[0]
                if vimeo_id.isdigit():
                    provider = 'vimeo'
                    embed_url = f"https://player.vimeo.com/video/{vimeo_id}"

            # Direct file fallback
            if not embed_url:
                # Basic whitelist for common video extensions
                if any(url.lower().endswith(ext) for ext in ('.mp4', '.webm', '.ogg', '.ogv', '.m3u8')):
                    provider = 'file'
                    embed_url = url
        except Exception:
            provider = None
            embed_url = None

    return render_template('video.html', url=url or None, provider=provider, embed_url=embed_url)
