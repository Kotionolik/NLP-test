# NLP-test

## Objective

Develop a solution capable of extracting information from Furniture Stores' websites.

It was decided to create a NER model tailored to identify the products to deal with that task.

## Training a NER model

I decided to train a NER model using spaCy library. While such a solution may be less suitable for training and fine-tuning models compared to Transformers, it has an advantage of being more lightweight compared to models trained using other means. Also, during testing the models' it was found out that the result is somewhat better using a spaCy model.

### Dataset

The data for the training was gained by crawling about ~200 websites from the list of URLs provided. The script was crawling through the website, as well as the upper domain, trying to find patterns commonly used by furniture store websites. The resulting data consisted of about a 1000 descriptions scraped from the websites. The scraping of some of the sites didn't yield any sort of information, either because they used different patterns, or because the site was simply unavailable for some reason. Some of the descriptions weren't suitable for the task, mostly due to the fact that the resulting data from the script did not always contain the name of the product. After using other publicly available data about the furniture store products and annotating the data, the dataset consisting of about 1300 entries was made.

### Training and testing

The model then was trained based on the dataset provided. The [resulting model](https://huggingface.co/KotioNolik/en_ner_model_furniture) had an accuracy of about 73%. Testing the model using some of the data that I found from the websites has shown that the model is mostly capable of identifying the product in the text.

For testing the model for the objective I made a website that created a table of products identified by the model from the URL provided. The script extracts the text from the HTML requested from the site, and afterwards it is sent to the model to identify the product names. The products are then displayed on the frontend. While it should work in theory, in practice, when the model got the text, it usually identifies completely wrong parts of the text as products (although the products themselves are also identified for the most of the time).

### The problem of training and possible solutions

One of the main problems identified with the training of the model is the overall structure of the product names. In general, they're quite long, contain many different adjectives and sometimes have their own name to further distinguish them from other products. Not to mention, while the product names may be somewhat similar on a single website, they may be entirely different on another website. In the end, that results in the model misidentifying product names. What are the possible solutions in that case?

1. **Trying to use only the furniture itself as a product**. While such a solution would probably stop the problem of mislabelling, I doubt it would be useful in terms of extracting furniture names. There may be dosens similar types of furniture, say, armchairs, so the model identifying only the type of the furniture will not yield any good results, as we won't know about the product any more than that.
2. **Expanding the dataset**. The dataset used during the training may simply be too small for the model to properly identify the product names. Therefore, expanding the dataset may be a feasible solution.
