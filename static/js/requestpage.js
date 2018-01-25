function validateForm() {
  if (document.forms["reqform"]["zipcode"].value.length!= 5) {
      alert("Invalid zipcode.  Please try again.");
      return false;
  }
}