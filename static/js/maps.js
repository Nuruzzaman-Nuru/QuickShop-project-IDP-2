// Maps initialization and location handling
function initMap() {
    const mapDiv = document.getElementById('map');
    const addressInput = document.getElementById('address');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    const form = document.querySelector('form');

    // If no map or related elements exist, exit gracefully
    if (!mapDiv || !addressInput) return;

    // Remove form validation for coordinates
    if (form) {
        form.addEventListener('submit', function(e) {
            // Allow form submission regardless of coordinates
            return true;
        });
    }

    // If the page has a map, initialize it with optional functionality
    if (mapDiv) {
        // Default to Dhaka, Bangladesh coordinates
        const defaultLocation = { lat: 23.8103, lng: 90.4125 };
        
        const map = new google.maps.Map(mapDiv, {
            zoom: 13,
            center: defaultLocation,
            mapTypeControl: false
        });

        const marker = new google.maps.Marker({
            map: map,
            position: defaultLocation,
            draggable: true
        });

        // Initialize Places Autocomplete if address input exists
        if (addressInput) {
            const autocomplete = new google.maps.places.Autocomplete(addressInput);
            autocomplete.bindTo('bounds', map);

            // Handle place selection
            autocomplete.addListener('place_changed', function() {
                const place = autocomplete.getPlace();
                if (!place.geometry) return;

                if (place.geometry.viewport) {
                    map.fitBounds(place.geometry.viewport);
                } else {
                    map.setCenter(place.geometry.location);
                    map.setZoom(17);
                }

                marker.setPosition(place.geometry.location);
                if (latInput && lngInput) {
                    latInput.value = place.geometry.location.lat();
                    lngInput.value = place.geometry.location.lng();
                }
                addressInput.value = place.formatted_address;
            });
        }

        // Handle marker drag if coordinate inputs exist
        if (latInput && lngInput) {
            marker.addListener('dragend', function() {
                const position = marker.getPosition();
                latInput.value = position.lat();
                lngInput.value = position.lng();
                
                // Update address using reverse geocoding
                const geocoder = new google.maps.Geocoder();
                geocoder.geocode({ location: position }, function(results, status) {
                    if (status === 'OK' && results[0]) {
                        addressInput.value = results[0].formatted_address;
                    }
                });
            });
        }
    }
}

// Location input initialization for other pages
function initLocationInput() {
    const useLocationSwitch = document.getElementById('useLocation');
    const locationFields = document.getElementById('locationFields');
    const locationInput = document.getElementById('locationInput');
    const latInput = document.getElementById('lat');
    const lngInput = document.getElementById('lng');

    if (!useLocationSwitch || !locationFields) return;

    // Initialize Places Autocomplete
    const autocomplete = new google.maps.places.Autocomplete(locationInput, {
        types: ['geocode']
    });

    // Handle place selection
    autocomplete.addListener('place_changed', () => {
        const place = autocomplete.getPlace();
        if (place.geometry) {
            latInput.value = place.geometry.location.lat();
            lngInput.value = place.geometry.location.lng();
            document.getElementById('filterForm').submit();
        }
    });

    // Handle location switch toggle
    useLocationSwitch.addEventListener('change', () => {
        if (useLocationSwitch.checked) {
            locationFields.style.display = 'flex';
            // Try to get current location
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        latInput.value = position.coords.latitude;
                        lngInput.value = position.coords.longitude;
                        // Reverse geocode to show address
                        const geocoder = new google.maps.Geocoder();
                        geocoder.geocode({
                            location: {
                                lat: position.coords.latitude,
                                lng: position.coords.longitude
                            }
                        }, (results, status) => {
                            if (status === 'OK' && results[0]) {
                                locationInput.value = results[0].formatted_address;
                                document.getElementById('filterForm').submit();
                            }
                        });
                    },
                    (error) => {
                        console.error('Geolocation error:', error);
                        locationFields.style.display = 'flex';
                    }
                );
            }
        } else {
            locationFields.style.display = 'none';
            latInput.value = '';
            lngInput.value = '';
            locationInput.value = '';
            document.getElementById('filterForm').submit();
        }
    });
}