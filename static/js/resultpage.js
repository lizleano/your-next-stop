function validateForm() {
	if ($('input:not(:has(:radio:active))').length) {
	  alert("Please evaluate all restaurants.");
	  return false;
	}
}	 