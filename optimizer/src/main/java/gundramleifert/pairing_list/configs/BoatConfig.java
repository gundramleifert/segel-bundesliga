package gundramleifert.pairing_list.configs;

import com.fasterxml.jackson.annotation.JsonProperty;

public class BoatConfig {

    private BoatConfig() {
    }

    @JsonProperty
    public String name = null;
    @JsonProperty
    public String color = null;
}
