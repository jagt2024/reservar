console.log(navigator);

console.log(navigator.geolocation);

getCurrentPosition
watchPosition
clearWatch

const options = {
  enableHighAccuracy: true,
  timeout: 5000,
  maximumAge: 0,
};

<html>
  <button id="find-me">Show my location</button><br />
  <p id="status"></p>
  <a id="map-link" target="_blank"></a>
  </html>

function geoFindMe() {
  const status = document.querySelector("#status");
  const mapLink = document.querySelector("#map-link");

  mapLink.href = "";
  mapLink.textContent = "";

  function success(position) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;

    status.textContent = "";
    mapLink.href = `https://www.openstreetmap.org/#map=18/${latitude}/${longitude}`;
    mapLink.textContent = `Latitude: ${latitude} °, Longitude: ${longitude} °`;

    console.log("Your current position is:");
    console.log(`Latitude : ${latitude}`);
    console.log(`Longitude: ${longitude}`);
    //console.log(`More or less ${crd.accuracy} meters.`);
  }

  function error(err) {
    status.textContent = "Unable to retrieve your location";
    console.warn(`ERROR(${err.code}): ${err.message}`);
  }
  
  if (!navigator.geolocation) {
    status.textContent = "Geolocation is not supported by your browser";
  } else {
    status.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(success, error);
  }
}

document.querySelector("#find-me").addEventListener("click", geoFindMe);

//El método que nos interesa es el getCurrentPosition el cual recibe de parametro un closure y nos devuelve la ubicación siempre y cuando nuestro usuario acepte los permisos.

//navigator.geolocation.getCurrentPosition(position => {
//  console.log(position);
//});

//navigator.geolocation.getCurrentPosition((position) => {
//  doSomething(position.coords.latitude, position.coords.longitude);
//  console.log(position);
//});

//si el usuario niega los permisos, bien, si queremos definir alguna acción en dado caso esto suceda, lo que podemos hacer es pasar de parametro un closure al método getCurrentPosition, este segundo parametro se ejecuta si nuestro usuario niega los permisos.

//navigator.geolocation.getCurrentPosition(position => {
//  console.log(position);
//}, e => {
//  console.log(e);
//});

//si necesitamos saber la ubicación cada cierto tiempo, para ello podemos usar al método watchPosition

//navigator.geolocation.watchPosition(position => {
//  console.log(position);
//});

//const watchID = navigator.geolocation.watchPosition((position) => {
//  doSomething(position.coords.latitude, position.coords.longitude);
//  console.log(position);
//});

//Este método nos devuelve un id que debemos usar con el método clearWatch si lo que necesitamos es dejar de recibir actualizaciones de la ubicación.

//let id = navigator.geolocation.watchPosition(position => {
//  console.log(position);
//});

//navigator.geolocation.clearWatch(id);