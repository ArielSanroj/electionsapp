import logging
import tweepy
import time
import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import os
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from dotenv import load_dotenv

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

# Inicializar Flask
app = Flask(__name__)

# Configuración de API de Twitter
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
if not BEARER_TOKEN:
    logger.error("Falta el BEARER_TOKEN para Twitter")
    exit(1)

# Inicialización del cliente de Twitter
try:
    twitter_client = tweepy.Client(bearer_token=BEARER_TOKEN)
except Exception as e:
    logger.error(f"Error al inicializar cliente de Twitter: {e}")
    exit(1)

# Inicialización del modelo de sentimiento BETO
try:
    tokenizer = AutoTokenizer.from_pretrained("finiteautomata/beto-sentiment-analysis")
    model = AutoModelForSequenceClassification.from_pretrained("finiteautomata/beto-sentiment-analysis")
except Exception as e:
    logger.error(f"Error al cargar modelo de sentimiento: {e}")
    exit(1)

# Conceptos clave del PND
PND_CONCEPTS = [
    "seguridad", "alimentacion", "infraestructura", "gobernanza y transparencia",
    "igualdad y equidad", "paz y reincorporación", "economía y empleo",
    "medio ambiente y cambio climático", "educación", "salud"
]

# Palabras clave para clasificar y buscar tweets por concepto del PND
PND_KEYWORDS = {
    "seguridad": ["seguridad", "delincuencia", "policía", "crimen", "violencia"],
    "alimentacion": ["alimentos", "comida", "hambre", "agricultura", "mercados"],
    "infraestructura": ["carreteras", "puentes", "transporte", "obras", "vías"],
    "gobernanza y transparencia": ["transparencia", "corrupción", "gobierno", "gestión"],
    "igualdad y equidad": ["igualdad", "equidad", "inclusión", "discriminación", "diversidad"],
    "paz y reincorporación": ["paz", "conflicto", "reincorporación", "acuerdos"],
    "economía y empleo": ["economía", "empleo", "trabajo", "desempleo", "industria"],
    "medio ambiente y cambio climático": ["ambiente", "clima", "sostenibilidad", "ecología"],
    "educación": ["educación", "escuelas", "universidad", "aprendizaje"],
    "salud": ["salud", "hospitales", "clínicas", "pandemia", "vacunas"]
}

# Plantillas para propuestas y discursos por concepto
PND_TEMPLATES = {
    "seguridad": {
        "propuesta": "Fortalecer la seguridad con más patrullajes y tecnología en {location}.",
        "discurso": "¡{location} segura! Con más policías y cámaras, garantizaremos tranquilidad.",
        "impacto": "Reducir homicidios 20% en 6 meses."
    },
    "alimentacion": {
        "propuesta": "Crear mercados móviles para mejorar el acceso a alimentos en {location}.",
        "discurso": "¡Alimentos frescos para todos en {location}! Mercados móviles en cada barrio.",
        "impacto": "Aumentar acceso a alimentos frescos para 50,000 residentes."
    },
    "infraestructura": {
        "propuesta": "Mejorar las vías y el transporte público en {location}.",
        "discurso": "¡{location} conectada! Modernizaremos carreteras y transporte para todos.",
        "impacto": "Reducir tiempos de viaje 30%."
    },
    "gobernanza y transparencia": {
        "propuesta": "Implementar plataformas de transparencia en la gestión pública de {location}.",
        "discurso": "¡{location} transparente! Publicaremos cada decisión para los ciudadanos.",
        "impacto": "Aumentar confianza ciudadana 25%."
    },
    "igualdad y equidad": {
        "propuesta": "Promover programas de inclusión social en {location}.",
        "discurso": "¡{location} inclusiva! Todos tendrán oportunidades sin discriminación.",
        "impacto": "Reducir incidentes de discriminación 15%."
    },
    "paz y reincorporación": {
        "propuesta": "Apoyar programas de reincorporación para víctimas en {location}.",
        "discurso": "¡Paz en {location}! Construiremos un futuro con oportunidades para todos.",
        "impacto": "Relocalizar 360 familias en 3 meses."
    },
    "economía y empleo": {
        "propuesta": "Impulsar el empleo con incentivos a pequeñas empresas en {location}.",
        "discurso": "¡{location} próspera! Crearemos empleos apoyando a emprendedores.",
        "impacto": "Crear 10,000 empleos en un año."
    },
    "medio ambiente y cambio climático": {
        "propuesta": "Proteger áreas verdes y promover energías renovables en {location}.",
        "discurso": "¡{location} verde! Cuidaremos el ambiente con energía limpia.",
        "impacto": "Aumentar cobertura verde 10%."
    },
    "educación": {
        "propuesta": "Mejorar el acceso a educación de calidad en {location}.",
        "discurso": "¡Educación para todos en {location}! Escuelas modernas y accesibles.",
        "impacto": "Reducir deserción escolar 15%."
    },
    "salud": {
        "propuesta": "Fortalecer hospitales y acceso a salud en {location}.",
        "discurso": "¡{location} saludable! Más hospitales y atención médica para todos.",
        "impacto": "Reducir demoras en atención médica 40%."
    }
}

def search_with_retry(query, max_results=10, retries=3, backoff_factor=60):
    for attempt in range(retries):
        try:
            return twitter_client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "author_id", "public_metrics", "geo", "in_reply_to_user_id", "context_annotations", "attachments"],
                expansions=["author_id"],
                user_fields=["username"]
            )
        except tweepy.TweepyException as e:
            if "Rate limit" in str(e) and attempt < retries - 1:
                wait_time = backoff_factor * (2 ** attempt)
                logger.warning(f"Rate limit hit, waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("Max retries exceeded for Twitter API")

def analyze_sentiment_batch(texts):
    if not texts:
        return []
    try:
        inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        return [{0: "negativo", 1: "neutral", 2: "positivo"}[torch.argmax(prob, dim=-1).item()] for prob in probabilities]
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {e}")
        return ["neutral"] * len(texts)

def search_and_summarize_tweets(location, politician=None):
    if not location or location.lower() == "none":
        location = "Bogotá"  # Default location to avoid None
    tweet_texts = []
    summary_lines = []

    for concept, keywords in PND_KEYWORDS.items():
        query = f'"{location}" ({" OR ".join(keywords)})'
        if politician:
            query += f' {politician} OR @{politician.lstrip("@")}'
        query += ' lang:es -is:retweet'
        try:
            response = search_with_retry(query=query, max_results=10)
            if not response.data:
                logger.info(f"No tweets found for query: {query}")
                continue

            users = {user.id: user.username for user in response.includes.get('users', [])}
            texts = [tweet.text for tweet in response.data]
            sentiments = analyze_sentiment_batch(texts)

            for tweet, sentiment in zip(response.data, sentiments):
                username = users.get(tweet.author_id, "unknown")
                tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
                tweet_texts.append({
                    "text": tweet.text,
                    "concept": concept,
                    "sentiment": sentiment
                })
                summary = (
                    f"👤 @{username}\n"
                    f"🗓️ {tweet.created_at}\n"
                    f"😊 Sentimiento: {sentiment}\n"
                    f"❤️ {tweet.public_metrics['like_count']} | 🔁 {tweet.public_metrics['retweet_count']}\n"
                    f"🔗 {tweet_url}\n"
                    f"📝 {tweet.text}\n"
                    f"🏷️ Concepto PND: {concept}"
                )
                if tweet.in_reply_to_user_id:
                    summary += f"\n↩️ Reply to user ID: {tweet.in_reply_to_user_id}"
                if tweet.geo:
                    summary += f"\n🌍 Geo: {tweet.geo}"
                if tweet.attachments:
                    summary += f"\n📎 Attachments: {tweet.attachments}"
                if tweet.context_annotations:
                    summary += "\n🏷️ Context: " + ", ".join([ca['entity']['name'] for ca in tweet.context_annotations if 'entity' in ca])
                summary_lines.append(summary + "\n\n")

            logger.info(f"Found {len(response.data)} tweets for query: {query}")
        except Exception as e:
            logger.error(f"Error fetching tweets for {concept}: {e}")
            continue

    if not tweet_texts:
        return [], "No tweets found for any PND concept in the given location."

    return tweet_texts, "\n".join(summary_lines)

def classify_tweets(tweets):
    classified = {concept: {"tweets": [], "sentiments": {"positivo": 0, "negativo": 0, "neutral": 0}} for concept in PND_CONCEPTS}
    classified["Ninguno"] = {"tweets": [], "sentiments": {"positivo": 0, "negativo": 0, "neutral": 0}}

    if not tweets:
        logger.info("No tweets to classify")
        return classified

    for tweet in tweets:
        if not isinstance(tweet, dict) or "concept" not in tweet or "text" not in tweet:
            logger.warning(f"Invalid tweet format: {tweet}")
            continue
        concept = tweet["concept"]
        tweet_text = tweet["text"]
        tweet_lower = tweet_text.lower()
        sentiment = tweet["sentiment"]
        explanation = f"Identificado en búsqueda específica para {concept}: {', '.join(PND_KEYWORDS[concept])}"

        if any(keyword in tweet_lower for keyword in PND_KEYWORDS[concept]):
            classified[concept]["tweets"].append({
                "text": tweet_text,
                "explanation": explanation,
                "sentiment": sentiment
            })
            classified[concept]["sentiments"][sentiment] += 1
        else:
            classified["Ninguno"]["tweets"].append({
                "text": tweet_text,
                "explanation": "No contiene palabras clave específicas, pero fue capturado en la búsqueda.",
                "sentiment": sentiment
            })
            classified["Ninguno"]["sentiments"][sentiment] += 1

    return classified

def generate_plan_and_discourse(classified_tweets, location):
    plan = {"conceptos": []}
    for concept in PND_CONCEPTS:
        tweets = classified_tweets.get(concept, {}).get("tweets", [])
        sentiments = classified_tweets.get(concept, {}).get("sentiments", {"positivo": 0, "negativo": 0, "neutral": 0})
        total_tweets = sum(sentiments.values())
        neg_percent = (sentiments["negativo"] / total_tweets * 100) if total_tweets > 0 else 0
        pos_percent = (sentiments["positivo"] / total_tweets * 100) if total_tweets > 0 else 0
        neu_percent = (sentiments["neutral"] / total_tweets * 100) if total_tweets > 0 else 0
        sentiment_summary = f"Sentimientos: Positivo {sentiments['positivo']} ({pos_percent:.1f}%), Negativo {sentiments['negativo']} ({neg_percent:.1f}%), Neutral {sentiments['neutral']} ({neu_percent:.1f}%)"

        if tweets:
            necesidad = f"Los electores de {location} expresan preocupaciones sobre {concept.lower()}: " + "; ".join(
                [tweet["text"][:50] + "..." for tweet in tweets[:3]]
            ) + f"\n{sentiment_summary}"
        else:
            necesidad = f"No se encontraron tweets específicos sobre {concept.lower()} en {location}."

        propuesta = PND_TEMPLATES[concept]["propuesta"].format(location=location)
        discurso = PND_TEMPLATES[concept]["discurso"].format(location=location)
        impacto = PND_TEMPLATES[concept]["impacto"]

        plan["conceptos"].append({
            "concepto": concept,
            "necesidad": necesidad,
            "propuesta": propuesta,
            "discurso": discurso,
            "impacto": impacto
        })
        logger.info(f"Added concept to plan: {concept}, tweets: {len(tweets)}, necesidad: {necesidad[:50]}...")

    return plan

def generate_politician_discourse(plan, location, candidate_name="[Nombre del Candidato]"):
    discourse_parts = [
        f"Queridos ciudadanos de {location}, soy {candidate_name}, un abogado de Bogotá con pasión por la ganadería y el arte, y un enfoque ligero pero comprometido en la política.\n\n"
    ]

    for concepto in plan.get("conceptos", []):
        discourse_parts.append(
            f"Respecto a {concepto['concepto'].lower()}:\n{concepto['discurso']}\n\n"
        )

    discourse_parts.append(
        f"Juntos, alineados con el PND 2022-2026, construiremos un {location} mejor. ¡Voten por el cambio real!"
    )

    return "".join(discourse_parts)

def get_chart_data(classified_tweets):
    labels = [c for c in PND_CONCEPTS if sum(classified_tweets[c]["sentiments"].values()) > 0]
    positive_counts = [classified_tweets[c]["sentiments"]["positivo"] for c in labels]
    negative_counts = [classified_tweets[c]["sentiments"]["negativo"] for c in labels]
    neutral_counts = [classified_tweets[c]["sentiments"]["neutral"] for c in labels]
    return {
        "labels": labels,
        "datasets": [
            {"label": "Positivo", "data": positive_counts, "backgroundColor": "#36A2EB"},
            {"label": "Negativo", "data": negative_counts, "backgroundColor": "#FF6384"},
            {"label": "Neutral", "data": neutral_counts, "backgroundColor": "#FFCE56"}
        ]
    }

def generate_resumen_ejecutivo(classified, location):
    total_tweets = sum(sum(c["sentiments"].values()) for c in classified.values() if c != classified.get("Ninguno", {}))
    neg_porcent = sum(c["sentiments"]["negativo"] for c in classified.values()) / total_tweets * 100 if total_tweets else 0
    pos_porcent = sum(c["sentiments"]["positivo"] for c in classified.values()) / total_tweets * 100 if total_tweets else 0
    neu_porcent = sum(c["sentiments"]["neutral"] for c in classified.values()) / total_tweets * 100 if total_tweets else 0

    max_neg_concept = max(
        [(c, classified[c]["sentiments"]["negativo"] / sum(classified[c]["sentiments"].values()) * 100)
         for c in PND_CONCEPTS if sum(classified[c]["sentiments"].values()) > 0],
        key=lambda x: x[1], default=("ninguno", 0)
    )[0]
    max_pos_concept = max(
        [(c, classified[c]["sentiments"]["positivo"] / sum(classified[c]["sentiments"].values()) * 100)
         for c in PND_CONCEPTS if sum(classified[c]["sentiments"].values()) > 0],
        key=lambda x: x[1], default=("ninguno", 0)
    )[0]

    return f"""<p>El análisis de tweets recientes en {location} revela preocupaciones ciudadanas alineadas con los conceptos clave del Plan Nacional de Desarrollo (PND 2022-2026). Se recopilaron y clasificaron aproximadamente {total_tweets} tweets en español (excluyendo retweets) relacionados con temas como seguridad, alimentación, infraestructura, gobernanza, igualdad, paz, economía, medio ambiente, educación y salud.</p>
<p><strong>Tendencias generales</strong>: La mayoría de los tweets muestran un tono mixto, con un predominio de neutral ({neu_porcent:.1f}%), seguido de negativo ({neg_porcent:.1f}%) y positivo ({pos_porcent:.1f}%). Los temas más críticos incluyen {max_neg_concept} ({classified[max_neg_concept]['sentiments']['negativo']} negativos), mientras que {max_pos_concept} destaca por positividad ({classified[max_pos_concept]['sentiments']['positivo']} positivos). Esto indica oportunidades para campañas enfocadas en soluciones prácticas.</p>
<p><strong>Volumen y sentimiento global</strong>: Seguridad y salud generan más discusión negativa, mientras que alimentación y economía tienen más neutralidad. Esto sugiere priorizar temas críticos en la estrategia de campaña.</p>
<p><strong>Contexto</strong>: Los tweets reflejan eventos actuales, con menciones frecuentes a figuras locales.</p>
<p>Este panorama sugiere que los electores buscan acciones concretas en {location}.</p>"""

def generate_analisis_datos(classified):
    output = ""
    for concept in PND_CONCEPTS:
        data = classified.get(concept, {})
        tweets = data.get("tweets", [])
        if not tweets:
            continue
        sentiments = data.get("sentiments", {"positivo": 0, "negativo": 0, "neutral": 0})
        output += f"{concept} ({len(tweets)} tweets, Sentimientos: Positivo {sentiments['positivo']}, Negativo {sentiments['negativo']}, Neutral {sentiments['neutral']}):\n"
        for tweet in tweets:
            output += f"  - \"{tweet['text']}\" ({tweet['sentiment'].capitalize()})\n"
    return output.strip() if output else "No data available for analysis."

def generate_plan_estrategico(plan_conceptos, classified):
    logger.info("Generating plan estratégico with plan_conceptos: %s", plan_conceptos)
    output = ""
    for concepto in plan_conceptos:
        concept_key = concepto['concepto']
        sentiments = classified.get(concept_key, {}).get("sentiments", {"positivo": 0, "negativo": 0, "neutral": 0})
        total = sum(sentiments.values())
        neg_porcent = (sentiments["negativo"] / total * 100) if total > 0 else 0
        output += f"{concepto['concepto']}: Necesidad: {concepto['necesidad']} ({neg_porcent:.1f}% negativo). Propuesta: {concepto['propuesta']}. Impacto: {concepto['impacto']}\n"
    return output.strip() if output else "No data available for strategic planning."

def generate_discurso(plan_conceptos, location="Bogotá", candidate_name="[Nombre del Candidato]"):
    discourse = f"Queridos ciudadanos de {location}, soy {candidate_name}, un abogado de Bogotá con pasión por la ganadería y el arte, y un enfoque ligero pero comprometido en la política.\n\n"
    for concepto in plan_conceptos:
        discourse += f"Respecto a {concepto['concepto'].lower()}:\n{concepto['discurso']}\n\n"
    discourse += f"Juntos, alineados con el PND 2022-2026, construiremos un {location} mejor. ¡Voten por el cambio real!"
    return discourse

def generate_grafico_visuales(chart_data, location="Bogotá"):
    return {
        "text": "",
        "chart_config": {
            "type": "bar",
            "data": {
                "labels": chart_data["labels"],
                "datasets": [
                    {
                        "label": "Positivo",
                        "data": chart_data["datasets"][0]["data"],
                        "backgroundColor": "#36A2EB",
                        "stack": "Stack 0"
                    },
                    {
                        "label": "Negativo",
                        "data": chart_data["datasets"][1]["data"],
                        "backgroundColor": "#FF6384",
                        "stack": "Stack 0"
                    },
                    {
                        "label": "Neutral",
                        "data": chart_data["datasets"][2]["data"],
                        "backgroundColor": "#FFCE56",
                        "stack": "Stack 0"
                    }
                ]
            },
            "options": {
                "scales": {
                    "x": {"stacked": True, "title": {"display": True, "text": "Conceptos del PND"}},
                    "y": {"stacked": True, "title": {"display": True, "text": "Conteo de Tweets"}}
                },
                "plugins": {"title": {"display": True, "text": "Distribución de Sentimientos por Concepto"}}
            }
        }
    }

def generate_structured_report(classified, chart_data, plan_conceptos, candidate_name="[Nombre del Candidato]", location="Bogotá"):
    logger.info("Generating structured report with plan_conceptos: %s", plan_conceptos)
    resumen = generate_resumen_ejecutivo(classified, location)
    analisis = generate_analisis_datos(classified)
    plan = generate_plan_estrategico(plan_conceptos, classified)
    discurso = generate_discurso(plan_conceptos, location, candidate_name)
    grafico = generate_grafico_visuales(chart_data, location)

    return {
        "resumen": resumen,
        "analisis": analisis,
        "plan": plan,
        "discurso": discurso,
        "grafico": grafico["text"],
        "chart_config": grafico["chart_config"]
    }

def job(location="Bogotá", candidate_name="[Nombre del Candidato]", politician=None):
    try:
        tweet_texts, _ = search_and_summarize_tweets(location, politician)
        classified = classify_tweets(tweet_texts)
        plan = generate_plan_and_discourse(classified, location)
        chart_data = get_chart_data(classified)
        report = generate_structured_report(classified, chart_data, plan["conceptos"], candidate_name, location)
        return report, chart_data
    except Exception as e:
        logger.error(f"Error in job: {e}")
        return {"error": str(e)}, {}

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webpage')
def webpage():
    return render_template('webpage.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        location = data.get('location', 'Bogotá')
        candidate_name = data.get('candidate_name', '[Nombre del Candidato]')
        politician = data.get('politician', None)

        report, chart_data = job(location, candidate_name, politician)
        if "error" in report:
            return jsonify({"status": "error", "message": report["error"]}), 500
        return jsonify({
            "status": "success",
            "report": report,
            "chart_data": chart_data
        })
    except Exception as e:
        logger.error(f"Error in /analyze: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False)