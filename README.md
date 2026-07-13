# Philips Spectral CT Webinar

Versione Streamlit pronta per Cloudflare R2 con:

- OTP inviato da `simone.terrani@philips.com`;
- registrazione automatica delle email non autorizzate tra le richieste;
- pulsante amministratore **Accetta account**, che abilita subito l'email;
- titolo e descrizione modificabili per ogni video;
- interfaccia responsive in stile Philips.

## Pubblicazione

1. Sostituire l'attuale `app.py` nel repository GitHub con quello incluso.
2. Copiare le chiavi di `.streamlit/secrets.toml.example` nei Secrets di Streamlit Cloud, inserendo i valori reali.
3. Aggiornare `requirements.txt` e riavviare l'app.

I file `authorized_accounts.json`, `richieste_accesso.json`, `video_metadata.json` e `feedback_webinar.json` vengono creati automaticamente nel bucket R2. `AUTHORIZED_EMAILS` resta l'elenco iniziale; gli account accettati dal pannello sono persistenti su R2.

## Nota SMTP Philips

Il codice supporta sia STARTTLS (porta 587, configurazione proposta) sia SSL. L'account aziendale deve essere autorizzato all'invio SMTP dal tenant Philips. Se SMTP AUTH è disabilitato, occorre usare il relay/servizio email approvato internamente e impostarne host, porta e credenziali nei Secrets.

## Avvio locale su Windows

Non aprire `app.py` con un doppio clic. Eseguire invece `avvia_app.bat`:

1. al primo avvio viene creato `.streamlit/secrets.toml` e aperto con Blocco note;
2. sostituire tutti i segnaposto con i valori reali e salvare;
3. eseguire nuovamente `avvia_app.bat`;
4. lasciare aperta la finestra del terminale mentre si usa l'app.

Il launcher installa le dipendenze e avvia Streamlit. Per arrestare il server premere `Ctrl+C`.
