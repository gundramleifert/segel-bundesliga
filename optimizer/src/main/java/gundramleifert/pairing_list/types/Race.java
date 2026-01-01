package gundramleifert.pairing_list.types;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Arrays;

public class Race {

    @JsonProperty
    public byte[] teams;

    public Race(){
    }

    public boolean hasLowerParticipants(int anzTeams){
        for (int i = 0; i < teams.length; i++) {
            if (teams[i]>=anzTeams)
                return true;
        }
        return false;
    }
    public int numParticipants(int anzTeams){
        int cnt = 0;
        for (int i = 0; i < teams.length; i++) {
            if (teams[i]<anzTeams)
                cnt++;
        }
        return cnt;
    }

    public Race(byte[] crews) {
        teams = crews;
    }

    public Race copy() {
        byte[] r = new byte[teams.length];
        System.arraycopy(teams, 0, r, 0, teams.length);
        return new Race(r);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        Race race = (Race) o;

        return Arrays.equals(teams, race.teams);
    }

    @Override
    public int hashCode() {
        return Arrays.hashCode(teams);
    }
}
