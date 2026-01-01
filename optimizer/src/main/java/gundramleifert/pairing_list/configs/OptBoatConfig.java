package gundramleifert.pairing_list.configs;

import com.fasterxml.jackson.annotation.JsonProperty;

public class OptBoatConfig extends OptConfig {

    private OptBoatConfig() {
    }

    @JsonProperty
    public int swapBoats;
    @JsonProperty
    public int swapRaces;
    @JsonProperty
    public double weightStayOnBoat;
    @JsonProperty
    public double weightStayOnShuttle;
    @JsonProperty
    public double weightChangeBetweenBoats;

    @Override
    public String toString() {
        return "OptBoatUsage{" +
                "swapBoats=" + swapBoats +
                ", swapRaces=" + swapRaces +
                ", weightStayOnBoat=" + weightStayOnBoat +
                ", weightStayOnShuttle=" + weightStayOnShuttle +
                ", weightChangeBetweenBoats=" + weightChangeBetweenBoats +
                ", loops=" + loops +
                ", individuals=" + individuals +
                ", earlyStopping=" + earlyStopping +
                ", saveEveryN=" + saveEveryN +
                ", showEveryN=" + showEveryN +
                '}';
    }
}
