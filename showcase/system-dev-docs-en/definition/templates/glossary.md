# Glossary

Defines the terms used in the requirements specification and the design document, in alphabetical order.

| Term | Definition |
|------|------------|
{% for t in this | sort(attribute="term") %}
| {{ t | anchor }}{{ t.term }} | {{ t.definition }} |
{% endfor %}
