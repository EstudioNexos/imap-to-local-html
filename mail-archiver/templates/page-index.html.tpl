<label>Archive information:</label>
{% for detail in info %}
    <div class="input-group mb-3">
        <div class="input-group-prepend">
            <span class="input-group-text" id="{{ detail.title }}-span">{{ detail.title }}</span>
        </div>
        <input type="text" class="form-control" id="{{ detail.title }}" aria-describedby="{{ detail.title }}-span" value="{{ detail.value }}" disabled />
    </div>
{% endfor %}
