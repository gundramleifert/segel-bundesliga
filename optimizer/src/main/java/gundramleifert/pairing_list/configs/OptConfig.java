package gundramleifert.pairing_list.configs;

import com.fasterxml.jackson.annotation.JsonProperty;

public abstract class OptConfig {
    @JsonProperty
    public int loops;
    @JsonProperty
    public int individuals;
    @JsonProperty
    public double earlyStopping = -1;
    @JsonProperty
    public int saveEveryN = -1;
    @JsonProperty
    public int showEveryN = 1000;

}
