(function() {
    var origin = '{{ request.host_url }}',
        key = {
            id: '{{ key.id }}',
            key: '{{ key.key }}'
        },
        query = {
            keyid: key.id,
            url: window.location.href,
            title: document.title
        },
        queryString = Object.keys(query).map(function(key) {
            var value = query[key];
            return encodeURIComponent(key) + '=' + encodeURIComponent(value);
        }).join('&');

    window.addEventListener('message', function(message) {
        if (message.origin === origin && message.data === 'onload') {
            message.source.postMessage(key.key, origin);
        }
    }, false);

    window.open(origin + '/post?' + queryString, undefined,
                'width=530,height=300,menubar=no,toolbar=no,scrollbars=yes');
})();
