This is a simple gateway for converting WSGI environment variables to HTTP-headers and forwarding the request.

It is useful when you need to pass forward Apache's ADFS_LOGIN (ADFS_PERSONID, ADSF_EMAIL, ADSF_FULLNAME or other ADSF_) variables, or if you want to emulate nginx's proxy_set_header directive.

At the moment it is very simple, but I'll support several nice features:
  * persistent connection to remote host
  * caching resources
 