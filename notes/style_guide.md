# Style Guide and Conventions
This documents the conventions on the style that is used to work on this codebase in order 
to establish a consistent environment, which is ease to understand and navigate and, 
therefore, easy to extend.

## Naming conventions
In general naming conventions as used by the django framework and other applied packages
such as django-rest-framework should be adapted. This section is about naming of things
that is not covered by any of the standard frameworks documentation because they are
very specific to BRIT.
### GeoDataSet model names
The GeoDataSet model is used to integrate datasets holding geodata of different heritage
and in different forms. For every third party dataset that is used to extend the database
a record of GeoDataset should be created because that is the way, it gets referenced 
within the tool. I.e. if any plugin holds a dataset that is referenced by the model name
```class HamburgRoadsideTrees(models.Model):```, creating a record of GeoDataSet with meta data is the way to 
integrate it into the whole system. It is important that the value of
```GeoDataSet.model_name``` will also be *HamburgRoadsideTrees*.

## Filters and Forms

### Form Fields
Use explicit field declaration in forms. 
(The use of proxy models might add additional columns to the table, which you don't expect)

### Crispy Forms
The package django-crispy-forms is used to facilitate most of the styling of the forms.
This is a crutch. The general aim is to deal with all UI and style questions in the
frontend. In the simple Django case that means in the templates. However, especially in
the beginning crispy forms can increase the workflow to quickly have a working interface
that does not look ugly.

In any template that includes a form, make sure to load
````
{% load crispy_forms_tags %}
````
The form can then be included with the following tag:
````
{% crispy form %}
````

### Form tags
By default, crispy will add form tags to all rendered forms. That means that any button
that is not defined within the FormHelper will not be outside of the form tags and not
perform the form action when pressed. To avoid this, make sure to always set 
````python
form_tag=False
````
in the form helper. In the template, the form tags as well as any buttons must be
included manually.

## APIViews
Avoid returning django's native JSONResponse object from API views. BRIT makes use of
django-rest-framework, which provides a more versatile Response object.
````python
from rest_framework.response import Response
````
