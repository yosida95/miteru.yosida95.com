(function() {
    var client = (function() {
        var Client = function() {};

        Client.prototype.set_secret = function(secret) {
            this.secret = secret;
        };

        Client.prototype.encode = function(params) {
            return Object.keys(params).map(function(key) {
                return key + '=' + encodeURIComponent(params[key]);
            }).join('&');
        };

        Client.prototype.sign = function(params) {
            var keys = Object.keys(params),
                qs = this.encode(params);

            var query = {};
            location.search.substring(1).split('&amp;').map(function(kv) {
                var kv = kv.split('='),
                    key = decodeURIComponent(kv[0]),
                    value = decodeURIComponent(kv[1]);
                query[key] = value;
            });
            if ('keyid' in query) {
                params['keyid'] = query['keyid'];
            }

            params['signed_keys'] = keys.join(',');
            params['signature'] = CryptoJS.HmacSHA1(qs, this.secret);
            return params;
        };

        Client.prototype.post = function(form, cb) {
            var data = this.sign({
                'title': form.title.value,
                'url': form.url.value,
                'comment': form.comment.value
            });
            data['csrf_token'] = form.csrf_token.value;

            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/post', true);
            xhr.setRequestHeader('Content-Type',
                                 'application/x-www-form-urlencoded');
            xhr.onreadystatechange = function() {
                if (xhr.readyState != 4) {
                    return;
                }

                cb(JSON.parse(xhr.responseText));
            };
            xhr.send(this.encode(data));
        };

        return new Client();
    })();

    window.addEventListener('message', function(message) {
        if (message.source == window.opener) {
            client.set_secret(message.data);
        }
    }, false);

    window.addEventListener('load', function() {
        window.opener.postMessage('onload', '*');

        var form = document.forms.post_form,
            comment = form.comment;

        comment.addEventListener('focus', function() {
            if (this.value === this.title) {
                this.value = '';
            }
            this.style.color = '#000000';
        }, false);

        comment.addEventListener('blur', function() {
            if (this.value === '') {
                this.value = this.title;
                this.style.color = '#808080';
            }
        }, false);

        form.addEventListener('submit', function(evt) {
            evt.preventDefault();  // cancel form submitting

            var message = document.getElementById('message');
            if (this.comment.value === this.comment.title) {
                this.comment.value = '';
            }

            message.style.color = '#000000';
            while (message.firstChild) {
                message.removeChild(message.firstChild);
            }
            message.appendChild(document.createTextNode('投稿中\u2026\u2026'));
            this.style.display = 'none';

            client.post(this, function(body) {
                if (body.result || !body.redo) {
                    setTimeout(window.close, 1500);
                }

                if (!body.result) {
                    message.style.color = '#ff0000';
                    if (body.redo) {
                        form.style.display = 'block';
                    }
                }

                while (message.firstChild) {
                    message.removeChild(message.firstChild);
                }
                message.appendChild(document.createTextNode(body.message));
            });

            return false;
        }, false);

        comment.focus();
    }, false);
})();
