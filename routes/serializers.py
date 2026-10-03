from rest_framework import serializers


class LocationField(serializers.CharField):
    def to_internal_value(self, data: object) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class RouteRequestSerializer(serializers.Serializer):
    start = LocationField(max_length=300, allow_blank=False)
    finish = LocationField(max_length=300, allow_blank=False)

    def validate(self, attrs: dict) -> dict:
        if attrs["start"].casefold() == attrs["finish"].casefold():
            raise serializers.ValidationError("Start and finish must be different.")
        return attrs


class LocationSerializer(serializers.Serializer):
    query = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class RouteGeometrySerializer(serializers.Serializer):
    distance_miles = serializers.FloatField()
    duration_hours = serializers.FloatField(
        help_text="Provider driving duration; excludes fueling and access time."
    )
    geometry = serializers.JSONField(help_text="GeoJSON LineString using [longitude, latitude] coordinates.")


class StationSerializer(serializers.Serializer):
    opis_truckstop_id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    retail_price_per_gallon = serializers.FloatField()
    geocoding_source = serializers.ChoiceField(choices=["census", "city_centroid"])


class FuelStopSerializer(StationSerializer):
    sequence = serializers.IntegerField()
    route_mile = serializers.FloatField()
    detour_miles = serializers.FloatField(help_text="Estimated round-trip station access distance.")
    gallons_purchased = serializers.FloatField()
    estimated_cost = serializers.FloatField()


class InitialFuelSerializer(serializers.Serializer):
    assumption = serializers.CharField()
    price_reference_station = StationSerializer()
    gallons_purchased = serializers.FloatField()
    estimated_cost = serializers.FloatField()
    reference_distance_miles = serializers.FloatField()


class FuelSummarySerializer(serializers.Serializer):
    estimated_driving_miles_including_detours = serializers.FloatField()
    estimated_gallons_consumed = serializers.FloatField()
    estimated_fuel_cost_usd = serializers.FloatField()
    estimated_arrival_fuel_gallons = serializers.FloatField()
    longest_leg_miles = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    start = LocationSerializer()
    finish = LocationSerializer()
    route = RouteGeometrySerializer()
    vehicle = serializers.DictField(child=serializers.FloatField())
    fuel_stops = FuelStopSerializer(many=True)
    initial_fueling = InitialFuelSerializer()
    fuel = FuelSummarySerializer()
    optimization = serializers.JSONField()
    warnings = serializers.ListField(child=serializers.CharField())
    map_url = serializers.CharField()
    map_expires_in_seconds = serializers.IntegerField()
