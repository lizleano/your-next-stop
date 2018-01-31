function validateResForm() {
  // alert($('#totalresults').val())      
  if ($('.active').length < $('#totalresults').val()){
    alert('Please evaluate all restaurants.');
    return false;
  }
} 