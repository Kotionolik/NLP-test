import spacy


nlp = spacy.load("./output/model-best")


def extract_entities(doc, entity_type):
    return [ent.text for ent in doc.ents if ent.label_ == entity_type]

entity_types = nlp.pipe_labels["ner"]

def extract_furniture_names(text):
    result = nlp(text)
    products = []
    entities = extract_entities(result, 'PRODUCT')
    for entity_type in entities:
        products.append(entity_type)
    return products