package gundramleifert.pairing_list.configs;

import com.fasterxml.jackson.annotation.JsonProperty;

public class OptMatchMatrixConfig extends OptConfig {
    @JsonProperty
    public int swapTeams;
    @JsonProperty
    public int maxBranches = 1;
    @JsonProperty
    public double factorLessParticipants=3.01;
    @JsonProperty
    public double factorTeamMissing =20.01;

//    @JsonProperty
//    public int merges;

    @Override
    public String toString() {
        return "OptMatchMatrix{" +
                "swapTeams=" + swapTeams +
                ", loops=" + loops +
                ", individuals=" + individuals +
                ", earlyStopping=" + earlyStopping +
                ", saveEveryN=" + saveEveryN +
                ", showEveryN=" + showEveryN +
                '}';
    }
}
